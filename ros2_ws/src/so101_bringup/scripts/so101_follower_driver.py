#!/usr/bin/python3
"""ROS 2 FollowJointTrajectory driver for a calibrated SO-101 follower."""

import glob
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

# The lightweight calibration venv contains the pure-Python Feetech SDK.  ROS 2
# Humble itself uses Python 3.10, so expose only this SDK path to the ROS node.
sdk_candidates = glob.glob(
    str(Path.home() / "lerobot_hf/.venv-calib/lib/python*/site-packages")
)
if sdk_candidates:
    # Keep ROS Humble's Python 3.10 packages (notably NumPy) ahead of the
    # Python 3.12 venv.  Only modules missing from the ROS environment, such
    # as the pure-Python Feetech SDK and pyserial, should come from this path.
    sys.path.append(sorted(sdk_candidates)[-1])

import rclpy
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint

try:
    import scservo_sdk as scs
except ImportError as exc:
    raise SystemExit(
        "scservo_sdk was not found. Expected it in "
        "~/lerobot_hf/.venv-calib/lib/python*/site-packages"
    ) from exc


JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
ARM_JOINTS = JOINT_NAMES[:5]
GRIPPER_JOINTS = JOINT_NAMES[5:]
MOTOR_IDS = {name: index + 1 for index, name in enumerate(JOINT_NAMES)}
URDF_LIMITS = {
    "shoulder_pan": (-1.91986, 1.91986),
    "shoulder_lift": (-1.74533, 1.74533),
    "elbow_flex": (-1.69, 1.69),
    "wrist_flex": (-1.65806, 1.65806),
    "wrist_roll": (-2.74385, 2.84121),
    "gripper": (-0.174533, 1.74533),
}
DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B91028413-if00"
DEFAULT_CALIBRATION = str(
    Path.home()
    / ".cache/huggingface/lerobot/calibration/robots/so_follower/so101_follower.json"
)
ADDR_MIN_POSITION = 9
ADDR_MAX_POSITION = 11
ADDR_HOMING_OFFSET = 31
ADDR_OPERATING_MODE = 33
ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_PRESENT_POSITION = 56
MODEL_NUMBER_STS3215 = 777
RESOLUTION = 4095.0


def duration_seconds(duration):
    return float(duration.sec) + float(duration.nanosec) * 1e-9


def decode_sign_magnitude(value, sign_bit):
    sign_mask = 1 << sign_bit
    magnitude = value & ~sign_mask
    return -magnitude if value & sign_mask else magnitude


class SO101FollowerDriver(Node):
    def __init__(self):
        super().__init__("so101_follower_driver")
        self.declare_parameter("port", DEFAULT_PORT)
        self.declare_parameter("calibration_file", DEFAULT_CALIBRATION)
        self.declare_parameter("enable_torque", False)
        self.declare_parameter("baudrate", 1_000_000)
        self.declare_parameter("state_publish_rate", 25.0)

        self.port_name = self.get_parameter("port").value
        calibration_file = Path(self.get_parameter("calibration_file").value).expanduser()
        self.enable_torque_on_start = bool(self.get_parameter("enable_torque").value)
        self.serial_lock = threading.RLock()
        self.active_lock = threading.Lock()
        self.active_goal = False
        self.torque_enabled = False
        self.last_positions = {name: 0.0 for name in JOINT_NAMES}
        self.calibration = self._load_calibration(calibration_file)

        if not os.path.exists(self.port_name):
            raise RuntimeError("Follower serial port does not exist: " + self.port_name)

        self.port = scs.PortHandler(self.port_name)
        self.packet = scs.PacketHandler(0)
        if not self.port.openPort():
            raise RuntimeError("Failed to open follower serial port: " + self.port_name)
        if not self.port.setBaudRate(int(self.get_parameter("baudrate").value)):
            self.port.closePort()
            raise RuntimeError("Failed to set follower baud rate")

        try:
            self._check_motors()
            self._check_hardware_calibration()
            self._disable_torque()
            raw_positions = self._read_raw_positions()
            self.last_positions = {
                name: self._raw_to_position(name, raw) for name, raw in raw_positions.items()
            }
            # Seed the exact measured encoder positions.  A manually parked
            # arm may sit just outside MoveIt's narrower planning limits.
            self._write_raw_positions(raw_positions)
            if self.enable_torque_on_start:
                self._set_position_mode()
                self._enable_torque()
                self.get_logger().warning(
                    "REAL HARDWARE ENABLED: MoveIt Execute will move the SO-101 follower"
                )
            else:
                self.get_logger().warning(
                    "Torque is OFF. Relaunch with enable_torque:=true to permit execution"
                )
        except Exception:
            self.port.closePort()
            raise

        callback_group = ReentrantCallbackGroup()
        self.arm_server = ActionServer(
            self,
            FollowJointTrajectory,
            "/arm_controller/follow_joint_trajectory",
            execute_callback=lambda handle: self._execute(handle, ARM_JOINTS),
            goal_callback=lambda request: self._goal_callback(request, ARM_JOINTS),
            cancel_callback=self._cancel_callback,
            callback_group=callback_group,
        )
        self.gripper_server = ActionServer(
            self,
            FollowJointTrajectory,
            "/gripper_controller/follow_joint_trajectory",
            execute_callback=lambda handle: self._execute(handle, GRIPPER_JOINTS),
            goal_callback=lambda request: self._goal_callback(request, GRIPPER_JOINTS),
            cancel_callback=self._cancel_callback,
            callback_group=callback_group,
        )
        self.joint_state_publisher = self.create_publisher(JointState, "/joint_states", 10)
        rate = max(5.0, float(self.get_parameter("state_publish_rate").value))
        self.state_timer = self.create_timer(1.0 / rate, self._publish_joint_state)
        self.get_logger().info("SO-101 follower connected on " + self.port_name)

    def _load_calibration(self, path):
        if not path.is_file():
            raise RuntimeError("Calibration JSON does not exist: " + str(path))
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if set(data) != set(JOINT_NAMES):
            raise RuntimeError("Calibration JSON has an unexpected motor list")
        for name, expected_id in MOTOR_IDS.items():
            if int(data[name]["id"]) != expected_id:
                raise RuntimeError("Calibration motor ID mismatch for " + name)
            if int(data[name]["range_min"]) >= int(data[name]["range_max"]):
                raise RuntimeError("Invalid calibration range for " + name)
        return data

    def _assert_comm(self, result, error, operation):
        if result != scs.COMM_SUCCESS:
            raise RuntimeError(operation + ": " + self.packet.getTxRxResult(result))
        if error:
            raise RuntimeError(operation + ": " + self.packet.getRxPacketError(error))

    def _read2(self, motor_id, address, operation):
        value, result, error = self.packet.read2ByteTxRx(self.port, motor_id, address)
        if result != scs.COMM_SUCCESS:
            raise RuntimeError(operation + ": " + self.packet.getTxRxResult(result))
        # STS3215 returns valid register data together with latched alarm bits.
        # Keep RViz state feedback alive, but expose the hardware warning. Writes
        # remain strict so an alarm cannot be ignored when enabling/moving motors.
        if error:
            self.get_logger().warning(
                operation + ": motor alarm: " + self.packet.getRxPacketError(error),
                throttle_duration_sec=2.0,
            )
        return int(value)

    def _write1(self, motor_id, address, value, operation, allow_alarm=False):
        result, error = self.packet.write1ByteTxRx(self.port, motor_id, address, int(value))
        if result != scs.COMM_SUCCESS:
            raise RuntimeError(operation + ": " + self.packet.getTxRxResult(result))
        if error:
            message = operation + ": motor alarm: " + self.packet.getRxPacketError(error)
            if not allow_alarm:
                raise RuntimeError(message)
            self.get_logger().warning(message, throttle_duration_sec=2.0)

    def _check_motors(self):
        with self.serial_lock:
            for name, motor_id in MOTOR_IDS.items():
                model, result, error = self.packet.ping(self.port, motor_id)
                if result != scs.COMM_SUCCESS:
                    raise RuntimeError("Ping " + name + ": " + self.packet.getTxRxResult(result))
                if error:
                    self.get_logger().warning(
                        "Ping " + name + ": motor alarm: " + self.packet.getRxPacketError(error)
                    )
                if int(model) != MODEL_NUMBER_STS3215:
                    raise RuntimeError(
                        "%s has model %s, expected STS3215 model %s"
                        % (name, model, MODEL_NUMBER_STS3215)
                    )

    def _check_hardware_calibration(self):
        mismatches = []
        with self.serial_lock:
            for name, motor_id in MOTOR_IDS.items():
                expected = self.calibration[name]
                actual_min = self._read2(motor_id, ADDR_MIN_POSITION, "Read min " + name)
                actual_max = self._read2(motor_id, ADDR_MAX_POSITION, "Read max " + name)
                raw_offset = self._read2(motor_id, ADDR_HOMING_OFFSET, "Read offset " + name)
                actual_offset = decode_sign_magnitude(raw_offset, 11)
                if (
                    actual_min != int(expected["range_min"])
                    or actual_max != int(expected["range_max"])
                    or actual_offset != int(expected["homing_offset"])
                ):
                    mismatches.append(name)
        if mismatches:
            raise RuntimeError(
                "Calibration JSON does not match motor memory: " + ", ".join(mismatches)
            )

    def _set_position_mode(self):
        with self.serial_lock:
            for name, motor_id in MOTOR_IDS.items():
                self._write1(motor_id, ADDR_OPERATING_MODE, 0, "Set position mode " + name)

    def _enable_torque(self):
        with self.serial_lock:
            for name, motor_id in MOTOR_IDS.items():
                self._write1(motor_id, ADDR_TORQUE_ENABLE, 1, "Enable torque " + name)
        self.torque_enabled = True

    def _disable_torque(self):
        errors = []
        with self.serial_lock:
            for name, motor_id in MOTOR_IDS.items():
                try:
                    self._write1(
                        motor_id,
                        ADDR_TORQUE_ENABLE,
                        0,
                        "Disable torque " + name,
                        allow_alarm=True,
                    )
                except Exception as exc:
                    errors.append(str(exc))
        self.torque_enabled = False
        if errors:
            raise RuntimeError("; ".join(errors))

    def _raw_to_position(self, name, raw):
        cal = self.calibration[name]
        if name == "gripper":
            fraction = (raw - cal["range_min"]) / (cal["range_max"] - cal["range_min"])
            lower, upper = URDF_LIMITS[name]
            return lower + fraction * (upper - lower)
        midpoint = (cal["range_min"] + cal["range_max"]) / 2.0
        return (raw - midpoint) * 2.0 * math.pi / RESOLUTION

    def _position_to_raw(self, name, position):
        lower, upper = URDF_LIMITS[name]
        if not lower - 1e-6 <= position <= upper + 1e-6:
            raise ValueError("%s target %.4f is outside [%.4f, %.4f]" % (name, position, lower, upper))
        cal = self.calibration[name]
        if name == "gripper":
            fraction = (position - lower) / (upper - lower)
            raw = cal["range_min"] + fraction * (cal["range_max"] - cal["range_min"])
        else:
            midpoint = (cal["range_min"] + cal["range_max"]) / 2.0
            raw = midpoint + position * RESOLUTION / (2.0 * math.pi)
        raw = int(round(raw))
        return max(int(cal["range_min"]), min(int(cal["range_max"]), raw))

    def _read_raw_positions(self):
        positions = {}
        with self.serial_lock:
            for name, motor_id in MOTOR_IDS.items():
                raw = self._read2(motor_id, ADDR_PRESENT_POSITION, "Read position " + name)
                positions[name] = decode_sign_magnitude(raw, 15)
        return positions

    def _read_positions(self):
        return {
            name: self._raw_to_position(name, raw)
            for name, raw in self._read_raw_positions().items()
        }

    def _write_raw_positions(self, raw_positions):
        writer = scs.GroupSyncWrite(self.port, self.packet, ADDR_GOAL_POSITION, 2)
        for name, raw in raw_positions.items():
            cal = self.calibration[name]
            raw = max(int(cal["range_min"]), min(int(cal["range_max"]), int(raw)))
            if not writer.addParam(MOTOR_IDS[name], [raw & 0xFF, (raw >> 8) & 0xFF]):
                raise RuntimeError("Failed to encode goal for " + name)
        with self.serial_lock:
            result = writer.txPacket()
        if result != scs.COMM_SUCCESS:
            raise RuntimeError("Goal write failed: " + self.packet.getTxRxResult(result))

    def _write_positions(self, positions):
        self._write_raw_positions(
            {name: self._position_to_raw(name, float(position)) for name, position in positions.items()}
        )

    def _publish_joint_state(self):
        try:
            positions = self._read_positions()
            self.last_positions = positions
        except Exception as exc:
            self.get_logger().error("Joint-state read failed: " + str(exc), throttle_duration_sec=2.0)
            positions = self.last_positions
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = JOINT_NAMES
        message.position = [positions[name] for name in JOINT_NAMES]
        self.joint_state_publisher.publish(message)

    def _goal_callback(self, request, expected_joints):
        if not self.torque_enabled:
            self.get_logger().error("Rejecting trajectory because torque is disabled")
            return GoalResponse.REJECT
        names = list(request.trajectory.joint_names)
        if set(names) != set(expected_joints) or len(names) != len(expected_joints):
            self.get_logger().error("Rejecting trajectory with incorrect joints: " + str(names))
            return GoalResponse.REJECT
        points = request.trajectory.points
        if not points:
            return GoalResponse.REJECT
        previous_time = -1.0
        for point in points:
            stamp = duration_seconds(point.time_from_start)
            if stamp <= previous_time or len(point.positions) != len(names):
                return GoalResponse.REJECT
            previous_time = stamp
            try:
                for index, name in enumerate(names):
                    self._position_to_raw(name, point.positions[index])
            except ValueError as exc:
                self.get_logger().error("Rejecting unsafe trajectory: " + str(exc))
                return GoalResponse.REJECT
        with self.active_lock:
            if self.active_goal:
                self.get_logger().error("Rejecting trajectory because another goal is active")
                return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_callback(self, _goal_handle):
        return CancelResponse.ACCEPT

    def _sample_trajectory(self, names, start_positions, points, elapsed):
        times = [duration_seconds(point.time_from_start) for point in points]
        previous_time = 0.0
        previous = [start_positions[name] for name in names]
        for point, point_time in zip(points, times):
            target = list(point.positions)
            if elapsed <= point_time:
                span = point_time - previous_time
                ratio = 1.0 if span <= 0.0 else (elapsed - previous_time) / span
                ratio = max(0.0, min(1.0, ratio))
                return {
                    name: previous[index] + (target[index] - previous[index]) * ratio
                    for index, name in enumerate(names)
                }
            previous_time = point_time
            previous = target
        return {name: previous[index] for index, name in enumerate(names)}

    def _make_result(self, code, message):
        result = FollowJointTrajectory.Result()
        result.error_code = code
        result.error_string = message
        return result

    def _execute(self, goal_handle, expected_joints):
        with self.active_lock:
            if self.active_goal:
                goal_handle.abort()
                return self._make_result(FollowJointTrajectory.Result.INVALID_GOAL, "Driver is busy")
            self.active_goal = True
        try:
            trajectory = goal_handle.request.trajectory
            names = list(trajectory.joint_names)
            points = trajectory.points
            start_positions = self._read_positions()
            total_time = duration_seconds(points[-1].time_from_start)
            start_time = time.monotonic()
            period = 0.02

            while rclpy.ok():
                if goal_handle.is_cancel_requested:
                    current_raw = self._read_raw_positions()
                    self._write_raw_positions(
                        {name: current_raw[name] for name in expected_joints}
                    )
                    goal_handle.canceled()
                    return self._make_result(FollowJointTrajectory.Result.SUCCESSFUL, "Cancelled")

                elapsed = min(time.monotonic() - start_time, total_time)
                desired = self._sample_trajectory(names, start_positions, points, elapsed)
                self._write_positions(desired)

                feedback = FollowJointTrajectory.Feedback()
                feedback.header.stamp = self.get_clock().now().to_msg()
                feedback.joint_names = names
                feedback.desired = JointTrajectoryPoint()
                feedback.desired.positions = [desired[name] for name in names]
                feedback.actual = JointTrajectoryPoint()
                feedback.actual.positions = [self.last_positions[name] for name in names]
                feedback.error = JointTrajectoryPoint()
                feedback.error.positions = [
                    desired[name] - self.last_positions[name] for name in names
                ]
                goal_handle.publish_feedback(feedback)

                if elapsed >= total_time:
                    break
                time.sleep(period)

            goal_handle.succeed()
            return self._make_result(FollowJointTrajectory.Result.SUCCESSFUL, "Completed")
        except Exception as exc:
            self.get_logger().error("Trajectory execution failed: " + str(exc))
            goal_handle.abort()
            return self._make_result(FollowJointTrajectory.Result.PATH_TOLERANCE_VIOLATED, str(exc))
        finally:
            with self.active_lock:
                self.active_goal = False

    def shutdown_hardware(self):
        if getattr(self, "port", None) is None:
            return
        try:
            if self.torque_enabled:
                self._disable_torque()
                self.get_logger().info("Follower torque disabled")
        except Exception as exc:
            self.get_logger().error("Failed to disable follower torque: " + str(exc))
        finally:
            self.port.closePort()


def main(args=None):
    rclpy.init(args=args)
    node = None
    executor = MultiThreadedExecutor(num_threads=4)
    try:
        node = SO101FollowerDriver()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.shutdown_hardware()
            node.destroy_node()
        executor.shutdown()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
