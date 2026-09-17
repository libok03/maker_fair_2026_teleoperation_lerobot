# Copyright 2025 nimiCurtis
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import os
import json

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _load_profiles(path):
    with open(path, encoding='utf-8') as profile_file:
        data = json.load(profile_file)
    return data.get('profiles', {})


def _resolve_profile(profiles, role, requested_profile, requested_port, requested_id):
    role_profiles = {
        name: values
        for name, values in profiles.items()
        if values.get('role') == role
    }

    if requested_profile != 'auto':
        if requested_profile not in role_profiles:
            available = ', '.join(sorted(role_profiles)) or '(none)'
            raise RuntimeError(
                f"Unknown {role} profile '{requested_profile}'. Available: {available}"
            )
        selected_name = requested_profile
        selected = role_profiles[selected_name]
    elif requested_port != 'auto' or requested_id != 'auto':
        # Explicit command-line overrides do not require a registered profile.
        selected_name = 'command-line override'
        selected = {}
    else:
        connected = [
            (name, values)
            for name, values in role_profiles.items()
            if os.path.exists(values['port'])
        ]
        if not connected:
            expected = '\n  '.join(
                f"{name}: {values['port']}"
                for name, values in sorted(role_profiles.items())
            )
            raise RuntimeError(
                f'No registered {role} arm is connected. Expected one of:\n  {expected}'
            )
        if len(connected) > 1:
            names = ', '.join(name for name, _ in connected)
            raise RuntimeError(
                f'Multiple {role} arms are connected ({names}). '
                f'Choose one with profile:=<name>.'
            )
        selected_name, selected = connected[0]

    port = requested_port if requested_port != 'auto' else selected.get('port')
    calibration_id = (
        requested_id if requested_id != 'auto' else selected.get('calibration_id')
    )
    if not port or not calibration_id:
        raise RuntimeError(
            'Both port and id must be supplied when bypassing the registered profiles.'
        )
    return selected_name, port, calibration_id


def _launch_bridge(context):
    role = LaunchConfiguration('type').perform(context)
    requested_profile = LaunchConfiguration('profile').perform(context)
    requested_port = LaunchConfiguration('port').perform(context)
    requested_id = LaunchConfiguration('id').perform(context)

    if role not in ('leader', 'follower'):
        raise RuntimeError("type must be either 'leader' or 'follower'")

    package_share = get_package_share_directory('so101_ros2_bridge')
    profiles_path = os.path.join(package_share, 'config', 'arm_profiles.json')
    profiles = _load_profiles(profiles_path)
    profile_name, port, calibration_id = _resolve_profile(
        profiles, role, requested_profile, requested_port, requested_id
    )
    config_path = os.path.join(package_share, 'config', f'so101_{role}_params.yaml')

    return [
        LogInfo(
            msg=(
                f'SO101 {role}: profile={profile_name}, port={port}, '
                f'calibration={calibration_id}'
            )
        ),
        Node(
            package='so101_ros2_bridge',
            executable=f'{role}_ros2_node',
            name=f'so101_{role}_interface',
            output='screen',
            parameters=[
                config_path,
                {
                    'type': role,
                    'port': port,
                    'id': calibration_id,
                },
            ],
            namespace=role,
        ),
    ]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'type',
                default_value='follower',
                description="Arm role: 'leader' or 'follower'",
            ),
            DeclareLaunchArgument(
                'profile',
                default_value='auto',
                description='Registered arm profile name, or auto',
            ),
            DeclareLaunchArgument(
                'port',
                default_value='auto',
                description='Serial port override, or auto',
            ),
            DeclareLaunchArgument(
                'id',
                default_value='auto',
                description='Calibration ID override, or auto',
            ),
            OpaqueFunction(function=_launch_bridge),
        ]
    )
