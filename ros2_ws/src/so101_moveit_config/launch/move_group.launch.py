from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from so101_moveit_config.configuration import moveit_parameters


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    hardware_type = LaunchConfiguration("hardware_type")
    controllers_file = LaunchConfiguration("controllers_file")
    params = moveit_parameters(hardware_type, controllers_file)

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("hardware_type", default_value="mock"),
            DeclareLaunchArgument("controllers_file", default_value=""),
            Node(
                package="moveit_ros_move_group",
                executable="move_group",
                output="screen",
                parameters=[*params, {"use_sim_time": use_sim_time}],
            ),
        ]
    )
