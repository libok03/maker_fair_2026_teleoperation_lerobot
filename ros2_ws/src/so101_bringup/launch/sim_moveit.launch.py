from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    headless = LaunchConfiguration("headless")
    use_rviz = LaunchConfiguration("rviz")
    world = LaunchConfiguration("world")
    controllers_file = PathJoinSubstitution(
        [FindPackageShare("so101_bringup"), "config", "controllers.yaml"]
    )
    default_world = PathJoinSubstitution(
        [FindPackageShare("so101_bringup"), "worlds", "empty.sdf"]
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_bringup"), "launch", "gazebo.launch.py"]
            )
        ),
        launch_arguments={
            "headless": headless,
            "use_sim_time": "true",
            "world": world,
        }.items(),
    )
    move_group = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_moveit_config"), "launch", "move_group.launch.py"]
            )
        ),
        launch_arguments={
            "use_sim_time": "true",
            "hardware_type": "gazebo",
            "controllers_file": controllers_file,
        }.items(),
    )
    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_moveit_config"), "launch", "moveit_rviz.launch.py"]
            )
        ),
        launch_arguments={
            "use_sim_time": "true",
            "hardware_type": "gazebo",
            "controllers_file": controllers_file,
        }.items(),
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("headless", default_value="false"),
            DeclareLaunchArgument("rviz", default_value="true"),
            DeclareLaunchArgument("world", default_value=default_world),
            gazebo,
            move_group,
            TimerAction(period=2.0, actions=[rviz]),
        ]
    )
