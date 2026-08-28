from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackagePrefix, FindPackageShare


def generate_launch_description():
    headless = LaunchConfiguration("headless")
    world = LaunchConfiguration("world")
    use_sim_time = LaunchConfiguration("use_sim_time")

    description_file = PathJoinSubstitution(
        [FindPackageShare("so101_description"), "urdf", "so101.urdf.xacro"]
    )
    controllers_file = PathJoinSubstitution(
        [FindPackageShare("so101_bringup"), "config", "controllers.yaml"]
    )
    default_world = PathJoinSubstitution(
        [FindPackageShare("so101_bringup"), "worlds", "empty.sdf"]
    )
    gz_launch = PathJoinSubstitution(
        [FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"]
    )
    robot_description = ParameterValue(
        Command(
            [
                "xacro ",
                description_file,
                " hardware_type:=gazebo controllers_file:=",
                controllers_file,
            ]
        ),
        value_type=str,
    )
    gazebo_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=[
            PathJoinSubstitution([FindPackagePrefix("so101_description"), "share"]),
            ":",
            EnvironmentVariable("GZ_SIM_RESOURCE_PATH", default_value=""),
        ],
    )

    gazebo_with_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_launch),
        launch_arguments={"gz_args": ["-r -v 3 ", world]}.items(),
        condition=UnlessCondition(headless),
    )
    gazebo_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_launch),
        launch_arguments={"gz_args": ["-r -s -v 3 ", world]}.items(),
        condition=IfCondition(headless),
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[
            {"robot_description": robot_description},
            {"use_sim_time": use_sim_time},
        ],
    )
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
    )
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-name",
            "so101",
            "-topic",
            "robot_description",
            "-z",
            "0.001",
        ],
        output="screen",
    )

    controller_spawners = [
        Node(
            package="controller_manager",
            executable="spawner",
            arguments=[name, "--controller-manager-timeout", "60"],
            output="screen",
        )
        for name in ("joint_state_broadcaster", "arm_controller", "gripper_controller")
    ]

    return LaunchDescription(
        [
            DeclareLaunchArgument("headless", default_value="false"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("world", default_value=default_world),
            gazebo_resource_path,
            gazebo_with_gui,
            gazebo_headless,
            clock_bridge,
            robot_state_publisher,
            spawn_robot,
            RegisterEventHandler(
                OnProcessExit(target_action=spawn_robot, on_exit=controller_spawners)
            ),
        ]
    )
