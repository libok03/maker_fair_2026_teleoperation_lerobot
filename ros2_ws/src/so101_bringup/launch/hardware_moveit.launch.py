from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    port = LaunchConfiguration("port")
    calibration_file = LaunchConfiguration("calibration_file")
    enable_torque = LaunchConfiguration("enable_torque")
    auto_recover = LaunchConfiguration("auto_recover")
    description_file = PathJoinSubstitution(
        [FindPackageShare("so101_description"), "urdf", "so101.urdf.xacro"]
    )
    robot_description = ParameterValue(
        Command(["xacro ", description_file, " hardware_type:=mock"]), value_type=str
    )

    driver = Node(
        package="so101_bringup",
        executable="so101_follower_driver.py",
        output="screen",
        parameters=[
            {
                "port": port,
                "calibration_file": calibration_file,
                "enable_torque": ParameterValue(enable_torque, value_type=bool),
                "auto_recover": ParameterValue(auto_recover, value_type=bool),
            }
        ],
    )
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description}],
    )
    move_group = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_moveit_config"), "launch", "move_group.launch.py"]
            )
        ),
        launch_arguments={"hardware_type": "mock"}.items(),
    )
    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so101_moveit_config"), "launch", "moveit_rviz.launch.py"]
            )
        ),
        launch_arguments={"hardware_type": "mock"}.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "port",
                default_value="/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B91028413-if00",
            ),
            DeclareLaunchArgument(
                "calibration_file",
                default_value=PathJoinSubstitution(
                    [
                        EnvironmentVariable("HOME"),
                        ".cache",
                        "huggingface",
                        "lerobot",
                        "calibration",
                        "robots",
                        "so_follower",
                        "so101_follower.json",
                    ]
                ),
            ),
            DeclareLaunchArgument("enable_torque", default_value="false"),
            DeclareLaunchArgument("auto_recover", default_value="true"),
            robot_state_publisher,
            driver,
            move_group,
            rviz,
        ]
    )
