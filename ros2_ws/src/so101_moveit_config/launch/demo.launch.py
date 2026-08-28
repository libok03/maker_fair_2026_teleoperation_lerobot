from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    control = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_bringup"), "launch", "ros2_control.launch.py"]
            )
        ),
        launch_arguments={"rviz": "false", "use_sim_time": "false"}.items(),
    )
    move_group = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_moveit_config"), "launch", "move_group.launch.py"]
            )
        )
    )
    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_moveit_config"), "launch", "moveit_rviz.launch.py"]
            )
        )
    )
    return LaunchDescription([control, move_group, rviz])
