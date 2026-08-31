#!/usr/bin/env python3
"""Safely move one calibrated SO-101 follower joint and return it home."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# Avoid importing optional ML dependencies (torch, OpenCV, etc.).
utils_package = types.ModuleType("lerobot.utils")
utils_package.__path__ = [str(REPO_ROOT / "src/lerobot/utils")]
utils_package.__package__ = "lerobot.utils"
sys.modules["lerobot.utils"] = utils_package

from lerobot.motors import Motor, MotorCalibration, MotorNormMode  # noqa: E402
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode  # noqa: E402


MOTORS = {
    "shoulder_pan": Motor(1, "sts3215", MotorNormMode.DEGREES),
    "shoulder_lift": Motor(2, "sts3215", MotorNormMode.DEGREES),
    "elbow_flex": Motor(3, "sts3215", MotorNormMode.DEGREES),
    "wrist_flex": Motor(4, "sts3215", MotorNormMode.DEGREES),
    "wrist_roll": Motor(5, "sts3215", MotorNormMode.DEGREES),
    "gripper": Motor(6, "sts3215", MotorNormMode.RANGE_0_100),
}

DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B91028413-if00"
DEFAULT_CALIBRATION = (
    Path.home()
    / ".cache/huggingface/lerobot/calibration/robots/so_follower/so101_follower.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--joint", choices=MOTORS, default="shoulder_pan")
    parser.add_argument(
        "--delta-ticks",
        type=int,
        default=40,
        help="Relative encoder movement (40 ticks is about 3.5 degrees)",
    )
    parser.add_argument("--duration", type=float, default=2.0, help="Seconds per direction")
    parser.add_argument("--rate", type=float, default=25.0, help="Command rate in Hz")
    return parser.parse_args()


def load_calibration(path: Path) -> dict[str, MotorCalibration]:
    with path.open(encoding="utf-8") as calibration_file:
        raw = json.load(calibration_file)

    if set(raw) != set(MOTORS):
        raise ValueError(f"Calibration motor names do not match: {sorted(raw)}")

    calibration = {name: MotorCalibration(**values) for name, values in raw.items()}
    for name, motor in MOTORS.items():
        if calibration[name].id != motor.id:
            raise ValueError(
                f"Calibration ID mismatch for {name}: "
                f"expected {motor.id}, got {calibration[name].id}"
            )
    return calibration


def interpolate(bus: FeetechMotorsBus, joint: str, start: int, end: int, duration: float, rate: float) -> None:
    steps = max(1, round(duration * rate))
    period = duration / steps
    deadline = time.monotonic()
    for step in range(1, steps + 1):
        position = round(start + (end - start) * step / steps)
        bus.sync_write("Goal_Position", {joint: position}, normalize=False, num_retry=2)
        deadline += period
        time.sleep(max(0.0, deadline - time.monotonic()))


def main() -> None:
    args = parse_args()
    if not os.path.exists(args.port):
        raise SystemExit(f"Port does not exist: {args.port}")
    if not os.access(args.port, os.R_OK | os.W_OK):
        raise SystemExit(f"No read/write permission for port: {args.port}")
    if not args.calibration.is_file():
        raise SystemExit(f"Calibration file does not exist: {args.calibration}")
    if args.delta_ticks == 0 or abs(args.delta_ticks) > 100:
        raise SystemExit("--delta-ticks must be between -100 and 100, excluding 0")
    if args.duration < 1.0:
        raise SystemExit("--duration must be at least 1.0 second")
    if not 5.0 <= args.rate <= 50.0:
        raise SystemExit("--rate must be between 5 and 50 Hz")

    calibration = load_calibration(args.calibration)
    bus = FeetechMotorsBus(port=args.port, motors=MOTORS, calibration=calibration)
    torque_enabled = False

    try:
        print("Connecting and checking follower motor IDs 1-6...")
        bus.connect()

        hardware_calibration = bus.read_calibration()
        mismatches = []
        for name, expected in calibration.items():
            actual = hardware_calibration[name]
            if (
                actual.homing_offset != expected.homing_offset
                or actual.range_min != expected.range_min
                or actual.range_max != expected.range_max
            ):
                mismatches.append(name)
        if mismatches:
            raise RuntimeError(
                "The JSON calibration does not match the motors: " + ", ".join(mismatches)
            )

        joint = args.joint
        bus.disable_torque(joint, num_retry=2)
        bus.write("Operating_Mode", joint, OperatingMode.POSITION.value, normalize=False, num_retry=2)

        start = int(bus.read("Present_Position", joint, normalize=False, num_retry=5))
        cal = calibration[joint]
        lower = cal.range_min + 25
        upper = cal.range_max - 25
        target = start + args.delta_ticks
        if not lower <= start <= upper:
            raise RuntimeError(
                f"Current {joint} position {start} is outside the safe calibrated interval "
                f"{lower}..{upper}. Move it by hand to a safe position first."
            )
        if not lower <= target <= upper:
            raise RuntimeError(
                f"Target {target} is outside the safe calibrated interval {lower}..{upper}. "
                "Use the opposite sign or a smaller --delta-ticks."
            )

        degrees = args.delta_ticks * 1000 / 4095
        print(
            f"\nJoint:  {joint}\n"
            f"Start:  {start} ticks\n"
            f"Target: {target} ticks ({degrees:+.1f} degrees)\n"
            f"Motion: {args.duration:.1f}s out, then {args.duration:.1f}s back\n"
        )
        print("Support the arm, clear the workspace, and keep a hand near the power switch.")
        if input("Type MOVE and press ENTER to start: ").strip() != "MOVE":
            print("Cancelled. No torque was enabled.")
            return

        # Seed the goal while torque is off so enabling torque cannot command a stale position.
        bus.write("Goal_Position", joint, start, normalize=False, num_retry=2)
        # Mark it first: even a partially successful enable command must be
        # followed by a best-effort torque-disable in the finally block.
        torque_enabled = True
        bus.enable_torque(joint, num_retry=2)

        interpolate(bus, joint, start, target, args.duration, args.rate)
        time.sleep(0.5)
        interpolate(bus, joint, target, start, args.duration, args.rate)
        time.sleep(0.3)
        print("Motion test completed; torque is being disabled.")
    except KeyboardInterrupt:
        print("\nInterrupted; disabling torque.")
        raise SystemExit(130) from None
    finally:
        if bus.is_connected:
            if torque_enabled:
                try:
                    bus.disable_torque(args.joint, num_retry=2)
                except Exception as exc:
                    print(f"WARNING: torque-disable command failed: {exc}", file=sys.stderr)
            bus.disconnect(disable_torque=False)


if __name__ == "__main__":
    main()
