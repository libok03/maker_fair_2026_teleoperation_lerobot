#!/usr/bin/env python3
"""Calibrate an SO-101 leader or follower without ML dependencies."""

from __future__ import annotations

import argparse
import json
import os
import sys
import types
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# Importing lerobot.utils normally also imports ML-only device helpers and torch.
# Expose the package path without running that unrelated __init__, while retaining
# the unmodified motor, serial, decorator, and utility modules below it.
utils_package = types.ModuleType("lerobot.utils")
utils_package.__path__ = [str(REPO_ROOT / "src/lerobot/utils")]
utils_package.__package__ = "lerobot.utils"
sys.modules["lerobot.utils"] = utils_package

from lerobot.motors import Motor, MotorCalibration, MotorNormMode  # noqa: E402
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Serial port or /dev/serial/by-id path")
    parser.add_argument("--role", choices=("leader", "follower"), default="leader")
    parser.add_argument("--id", default=None, help="Calibration file identifier")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory in which to save the LeRobot-compatible calibration JSON",
    )
    return parser.parse_args()


def make_bus(port: str) -> FeetechMotorsBus:
    return FeetechMotorsBus(
        port=port,
        motors={
            "shoulder_pan": Motor(1, "sts3215", MotorNormMode.DEGREES),
            "shoulder_lift": Motor(2, "sts3215", MotorNormMode.DEGREES),
            "elbow_flex": Motor(3, "sts3215", MotorNormMode.DEGREES),
            "wrist_flex": Motor(4, "sts3215", MotorNormMode.DEGREES),
            "wrist_roll": Motor(5, "sts3215", MotorNormMode.DEGREES),
            "gripper": Motor(6, "sts3215", MotorNormMode.RANGE_0_100),
        },
    )


def set_wrapped_half_turn_homings(bus: FeetechMotorsBus) -> dict[str, int]:
    """Set half-turn homings while handling encoder wraparound safely."""
    bus.reset_calibration()
    positions = bus.sync_read("Present_Position", normalize=False, num_retry=5)
    offsets: dict[str, int] = {}

    print("\nHoming values:")
    for motor, position in positions.items():
        model = bus.motors[motor].model
        resolution = bus.model_resolution_table[model]
        half_turn = int((resolution - 1) / 2)
        wrapped_position = int(position) % resolution
        offset = wrapped_position - half_turn
        if offset > half_turn:
            offset -= resolution
        # Sign-magnitude homing offsets cannot represent -2048 on a 12-bit
        # STS3215. One encoder tick away from exact center is harmless.
        offset = max(-half_turn, min(half_turn, offset))
        offsets[motor] = offset
        print(
            f"  {motor:15s} raw={int(position):5d} "
            f"wrapped={wrapped_position:4d} offset={offset:+5d}"
        )

    for motor, offset in offsets.items():
        bus.write("Homing_Offset", motor, offset)
    return offsets


def main() -> None:
    args = parse_args()
    device_id = args.id or f"so101_{args.role}"
    output_dir = args.output_dir
    if output_dir is None:
        calibration_root = Path.home() / ".cache/huggingface/lerobot/calibration"
        output_dir = (
            calibration_root / "teleoperators/so_leader"
            if args.role == "leader"
            else calibration_root / "robots/so_follower"
        )
    if not os.path.exists(args.port):
        raise SystemExit(f"Port does not exist: {args.port}")
    if not os.access(args.port, os.R_OK | os.W_OK):
        raise SystemExit(f"No read/write permission for port: {args.port}")

    bus = make_bus(args.port)
    handshake_succeeded = False
    try:
        print("Connecting and checking STS3215 motor IDs 1-6...")
        bus.connect()
        handshake_succeeded = True
        bus.disable_torque()
        bus.configure_motors()
        for motor in bus.motors:
            bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)

        input(
            "\nMove every joint near the middle of its range. "
            "Center wrist_roll as well, then press ENTER..."
        )
        homing_offsets = set_wrapped_half_turn_homings(bus)

        full_turn_motor = "wrist_roll"
        ranged_motors = [name for name in bus.motors if name != full_turn_motor]
        print(
            "\nSlowly move each listed joint through its full safe range:\n"
            "  shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, gripper\n"
            "Do not force mechanical stops. Press ENTER when all ranges are covered."
        )
        range_mins, range_maxes = bus.record_ranges_of_motion(ranged_motors)
        range_mins[full_turn_motor] = 0
        range_maxes[full_turn_motor] = 4095

        calibration = {
            name: MotorCalibration(
                id=motor.id,
                drive_mode=0,
                homing_offset=int(homing_offsets[name]),
                range_min=int(range_mins[name]),
                range_max=int(range_maxes[name]),
            )
            for name, motor in bus.motors.items()
        }
        bus.write_calibration(calibration)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{device_id}.json"
        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(
                {name: asdict(values) for name, values in calibration.items()},
                output_file,
                indent=4,
            )
            output_file.write("\n")
        print(f"\nCalibration saved to {output_path}")
    except KeyboardInterrupt:
        print("\nCalibration cancelled; disabling torque and closing the port.")
        raise SystemExit(130) from None
    finally:
        if bus.is_connected:
            if handshake_succeeded:
                bus.disconnect(disable_torque=True)
            else:
                # A failed handshake leaves the SDK port open, but motors are not
                # known to be reachable. Close it without issuing six torque writes.
                bus.port_handler.closePort()


if __name__ == "__main__":
    main()
