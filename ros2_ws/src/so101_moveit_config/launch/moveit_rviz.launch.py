from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from pathlib import Path

from so101_moveit_config.configuration import moveit_parameters


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    hardware_type = LaunchConfiguration("hardware_type")
    controllers_file = LaunchConfiguration("controllers_file")
    params = moveit_parameters(hardware_type, controllers_file)
    rviz_config = (
        Path(get_package_share_directory("so101_moveit_config"))
        / "rviz"
        / "moveit.rviz"
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("hardware_type", default_value="mock"),
            DeclareLaunchArgument("controllers_file", default_value=""),
            Node(
                package="rviz2",
                executable="rviz2",
                name="moveit_rviz",
                arguments=["-d", str(rviz_config)],
                output="screen",
                parameters=[*params, {"use_sim_time": use_sim_time}],
            ),
        ]
    )
