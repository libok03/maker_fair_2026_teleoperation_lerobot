from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import Command
from launch_ros.parameter_descriptions import ParameterValue


def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def moveit_parameters(hardware_type="mock", controllers_file=""):
    description_share = Path(get_package_share_directory("so101_description"))
    config_share = Path(get_package_share_directory("so101_moveit_config"))
    description_file = description_share / "urdf" / "so101.urdf.xacro"

    xacro_command = [
        "xacro ",
        str(description_file),
        " hardware_type:=",
        hardware_type,
    ]
    if controllers_file:
        xacro_command.extend([" controllers_file:=", controllers_file])

    robot_description = {
        "robot_description": ParameterValue(Command(xacro_command), value_type=str)
    }
    robot_description_semantic = {
        "robot_description_semantic": (config_share / "config" / "so101.srdf").read_text(
            encoding="utf-8"
        )
    }
    robot_description_kinematics = {
        "robot_description_kinematics": _load_yaml(
            config_share / "config" / "kinematics.yaml"
        )
    }

    joint_limits = _load_yaml(config_share / "config" / "joint_limits.yaml")
    cartesian_limits = _load_yaml(config_share / "config" / "pilz_cartesian_limits.yaml")
    robot_description_planning = {
        "robot_description_planning": {**joint_limits, **cartesian_limits}
    }

    planning_pipelines = {
        "planning_pipelines": ["ompl", "pilz_industrial_motion_planner", "stomp"],
        "default_planning_pipeline": "ompl",
        "ompl": _load_yaml(config_share / "config" / "ompl_planning.yaml"),
        "pilz_industrial_motion_planner": _load_yaml(
            config_share
            / "config"
            / "pilz_industrial_motion_planner_planning.yaml"
        ),
        "stomp": _load_yaml(config_share / "config" / "stomp_planning.yaml"),
    }

    controller_parameters = _load_yaml(
        config_share / "config" / "moveit_controllers.yaml"
    )
    trajectory_execution = {
        "trajectory_execution.allowed_execution_duration_scaling": 1.2,
        "trajectory_execution.allowed_goal_duration_margin": 0.5,
        "trajectory_execution.allowed_start_tolerance": 0.01,
        "moveit_manage_controllers": False,
    }
    planning_scene_monitor = {
        "publish_planning_scene": True,
        "publish_geometry_updates": True,
        "publish_state_updates": True,
        "publish_transforms_updates": True,
        "publish_robot_description": True,
        "publish_robot_description_semantic": True,
    }

    return [
        robot_description,
        robot_description_semantic,
        robot_description_kinematics,
        robot_description_planning,
        planning_pipelines,
        controller_parameters,
        trajectory_execution,
        planning_scene_monitor,
    ]
