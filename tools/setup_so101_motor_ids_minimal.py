#!/usr/bin/env python3
"""Assign SO-101 leader or follower motor IDs 6 through 1."""

from __future__ import annotations

import argparse

from calibrate_so101_leader_minimal import make_bus


SETUP_ORDER = [
    ("gripper", 6),
    ("wrist_roll", 5),
    ("wrist_flex", 4),
    ("elbow_flex", 3),
    ("shoulder_lift", 2),
    ("shoulder_pan", 1),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Serial port or /dev/serial/by-id path")
    parser.add_argument("--role", choices=("leader", "follower"), default="leader")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bus = make_bus(args.port)

    print(
        f"Configuring SO-101 {args.role} motors.\n"
        "IMPORTANT: connect exactly ONE motor to the controller at each step.\n"
        "Power OFF before changing a 3-pin cable, then power ON before pressing ENTER.\n"
    )

    try:
        for motor_name, target_id in SETUP_ORDER:
            input(
                f"Connect ONLY '{motor_name}' (target ID {target_id}), "
                "power it on, then press ENTER..."
            )
            bus.setup_motor(motor_name)
            print(f"OK: '{motor_name}' configured as ID {target_id} at 1,000,000 baud.\n")
    except KeyboardInterrupt:
        print("\nMotor setup cancelled. The motors already completed keep their assigned IDs.")
        raise SystemExit(130) from None
    finally:
        # setup_motor leaves the serial port open. Close it directly because only
        # one motor is attached and writing to all six configured IDs would fail.
        if bus.is_connected:
            bus.port_handler.closePort()

    print(f"All six {args.role} motors are configured. Reconnect the full daisy chain.")


if __name__ == "__main__":
    main()
