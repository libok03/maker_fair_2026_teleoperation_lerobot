#!/usr/bin/env python3
"""Read voltage and configured voltage limits from SO-101 STS3215 motors."""

import argparse
import os

import scservo_sdk as scs


DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B91028413-if00"
ADDR_MAX_VOLTAGE_LIMIT = 14
ADDR_MIN_VOLTAGE_LIMIT = 15
ADDR_PRESENT_VOLTAGE = 62


def read_byte(packet, port, motor_id, address):
    value, result, error = packet.read1ByteTxRx(port, motor_id, address)
    comm_message = packet.getTxRxResult(result)
    alarm_message = packet.getRxPacketError(error) if error else "OK"
    return int(value), result == scs.COMM_SUCCESS, comm_message, alarm_message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=1_000_000)
    args = parser.parse_args()

    if not os.path.exists(args.port):
        raise SystemExit("Port does not exist: " + args.port)

    port = scs.PortHandler(args.port)
    packet = scs.PacketHandler(0)
    if not port.openPort():
        raise SystemExit("Could not open the port. Stop the ROS driver first: " + args.port)
    try:
        if not port.setBaudRate(args.baudrate):
            raise SystemExit("Could not set baud rate")

        print("ID  JOINT            VOLTAGE   CONFIGURED LIMITS   STATUS")
        names = [
            "shoulder_pan",
            "shoulder_lift",
            "elbow_flex",
            "wrist_flex",
            "wrist_roll",
            "gripper",
        ]
        for motor_id, name in enumerate(names, start=1):
            voltage, ok, comm, alarm = read_byte(
                packet, port, motor_id, ADDR_PRESENT_VOLTAGE
            )
            minimum, min_ok, min_comm, _ = read_byte(
                packet, port, motor_id, ADDR_MIN_VOLTAGE_LIMIT
            )
            maximum, max_ok, max_comm, _ = read_byte(
                packet, port, motor_id, ADDR_MAX_VOLTAGE_LIMIT
            )
            if not (ok and min_ok and max_ok):
                print(
                    f"{motor_id:2d}  {name:15s} communication failed: "
                    f"{comm}; {min_comm}; {max_comm}"
                )
                continue
            print(
                f"{motor_id:2d}  {name:15s} {voltage / 10:5.1f} V   "
                f"{minimum / 10:4.1f}..{maximum / 10:4.1f} V       {alarm}"
            )
    finally:
        port.closePort()


if __name__ == "__main__":
    main()
