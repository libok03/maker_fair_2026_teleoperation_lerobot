from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_rviz = LaunchConfiguration("rviz")
    use_sim_time = LaunchConfiguration("use_sim_time")
    description_file = PathJoinSubstitution(
        [FindPackageShare("so101_description"), "urdf", "so101.urdf.xacro"]
    )
    controllers_file = PathJoinSubstitution(
        [FindPackageShare("so101_bringup"), "config", "controllers.yaml"]
    )
    rviz_config = PathJoinSubstitution(
        [FindPackageShare("so101_description"), "rviz", "display.rviz"]
    )
    robot_description = ParameterValue(
        Command(["xacro ", description_file, " hardware_type:=mock"]), value_type=str
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("rviz", default_value="true"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                output="screen",
                parameters=[
                    {"robot_description": robot_description},
                    {"use_sim_time": use_sim_time},
                ],
            ),
            Node(
                package="controller_manager",
                executable="ros2_control_node",
                output="screen",
                parameters=[
                    {"robot_description": robot_description},
                    controllers_file,
                    {"use_sim_time": use_sim_time},
                ],
            ),
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=[
                    "joint_state_broadcaster",
                    "--controller-manager-timeout",
                    "60",
                ],
                output="screen",
            ),
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=["arm_controller", "--controller-manager-timeout", "60"],
                output="screen",
            ),
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=["gripper_controller", "--controller-manager-timeout", "60"],
                output="screen",
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                arguments=["-d", rviz_config],
                condition=IfCondition(use_rviz),
                output="screen",
            ),
        ]
    )
