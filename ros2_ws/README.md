# SO-101 ROS 2 / Gazebo Harmonic / MoveIt 2

ROS 2 Humble에서 SO-101을 RViz, `ros2_control`, Gazebo Harmonic, MoveIt 2와 함께
사용하기 위한 워크스페이스입니다. MoveIt 계획 파이프라인은 OMPL, Pilz, STOMP를
모두 등록합니다.

## 패키지

- `so101_description`: 공식 SO-101 new-calibration URDF, STL mesh, RViz 표시
- `so101_bringup`: mock/Gazebo `ros2_control`, 컨트롤러, Harmonic 월드, 통합 launch
- `so101_moveit_config`: SRDF, 위치 우선 KDL IK, OMPL/Pilz/STOMP, MoveIt RViz

모델은 TheRobotStudio/SO-ARM100 저장소의
`Simulation/SO101/so101_new_calib.urdf`와 STL을 기준으로 하며, 가져온 시점의
upstream commit은 `7629d2ad9853d10fb903093a33ef6114099d97e5`입니다. mesh URI와
ROS 2 제어 태그만 패키지 구조에 맞게 확장했습니다.

## 1. 의존성 설치

먼저 ROS 2 / MoveIt 기본 패키지를 설치합니다.

```bash
sudo apt update
sudo apt install \
  python3-rosdep python3-vcstool \
  ros-humble-moveit \
  ros-humble-ros2-control ros-humble-ros2-controllers \
  ros-humble-joint-state-publisher-gui \
  ros-humble-xacro ros-humble-stomp
```

Humble의 ROS 공식 저장소 기본 조합은 Gazebo Fortress입니다. Harmonic을 지정해서
사용하려면 아래처럼 Gazebo 공식 `packages.osrfoundation.org` 저장소를 먼저
등록합니다.

```bash
sudo apt-get update
sudo apt-get install -y curl lsb-release gnupg

sudo curl https://packages.osrfoundation.org/gazebo.gpg \
  --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

sudo apt-get update
```

그 다음 비공식 Humble/Harmonic ROS 연동 바이너리를 설치합니다.

```bash
sudo apt-get install -y gz-harmonic \
  ros-humble-ros-gzharmonic \
  ros-humble-ros-gzharmonic-bridge
```

`ros-humble-ros-gzharmonic*`은 `ros-humble-ros-gz*`(Fortress)와 충돌하므로 두
계열을 섞지 않습니다. Harmonic용 `gz_ros2_control`과 Humble에서 별도 제공되지 않는
MoveIt STOMP 플러그인은 이 워크스페이스에서 소스 빌드합니다.

검증한 `gz_ros2_control`과 Humble 호환 수정이 적용된 `stomp_moveit` 소스는
`src/`에 포함되어 있습니다. `dependencies-humble.repos`는 사용한 upstream revision을
기록하기 위한 파일이므로 일반적인 빌드에서는 `vcs import`를 다시 실행하지 않습니다.

```bash
cd maker_fair_2026_teleoperation_lerobot/ros2_ws
source /opt/ros/humble/setup.bash
export GZ_VERSION=harmonic
rosdep install --from-paths src --ignore-src -r -y \
  --rosdistro humble \
  --skip-keys="ros_gz_bridge ros_gz_sim stomp_moveit"
```

## 2. 빌드

Harmonic 헤더를 선택하도록 빌드할 때도 `GZ_VERSION`을 유지합니다.

```bash
cd maker_fair_2026_teleoperation_lerobot/ros2_ws
source /opt/ros/humble/setup.bash
export GZ_VERSION=harmonic
colcon build --symlink-install \
  --packages-up-to so101_moveit_config \
  --cmake-args -DBUILD_TESTING=OFF -DBUILD_STOMP_EXAMPLE=OFF
source install/setup.bash
```

설치와 overlay가 정상인지 다음 명령으로 먼저 확인할 수 있습니다.

```bash
gz sim --version
ros2 pkg prefix ros_gz_sim
ros2 pkg prefix ros_gz_bridge
ros2 pkg prefix gz_ros2_control
```

마지막 명령만 실패하면 `export GZ_VERSION=harmonic`을 확인하고 워크스페이스를 다시
빌드한 다음 `install/setup.bash`를 source합니다.

## 3. 실행

### RViz URDF 확인

```bash
ros2 launch so101_description display.launch.py
```

### ros2_control mock hardware

```bash
ros2 launch so101_bringup ros2_control.launch.py
ros2 control list_controllers
```

### Gazebo Harmonic + ros2_control

```bash
ros2 launch so101_bringup gazebo.launch.py
```

GUI 없이 실행하려면 `headless:=true`를 추가합니다.

### MoveIt 2 + mock hardware

```bash
ros2 launch so101_moveit_config demo.launch.py
```

### Gazebo + MoveIt 통합

```bash
ros2 launch so101_bringup sim_moveit.launch.py
```

### 실제 팔로워 + MoveIt + RViz

먼저 캘리브레이션 JSON을 복원하고 `~/lerobot_hf/.venv-calib`에 설치된 순수 Python
Feetech SDK를 사용합니다. 토크 없이 ID, 캘리브레이션 및 RViz 상태 반영을 확인합니다.

```bash
ros2 launch so101_bringup hardware_moveit.launch.py
```

실제 실행 전 팔을 받치고 작업 공간과 비상 전원 차단 수단을 확보한 뒤 실행합니다.

```bash
ros2 launch so101_bringup hardware_moveit.launch.py enable_torque:=true
```

드라이버는 `/arm_controller/follow_joint_trajectory`와
`/gripper_controller/follow_joint_trajectory`를 받아 캘리브레이션된 STS3215 raw 값으로
변환하고, 실제 위치를 `/joint_states`로 RViz에 되돌려 보냅니다. 시작할 때 JSON과
모터 내부 offset/range가 다르면 토크를 켜지 않고 종료합니다.

RViz MotionPlanning 패널의 `Planning Library`에서 다음 파이프라인을 선택합니다.

- `ompl`: 기본값. planner ID는 `RRTConnectkConfigDefault`, `RRTstarkConfigDefault`,
  `PRMkConfigDefault`
- `pilz_industrial_motion_planner`: `PTP`, `LIN`, `CIRC`
- `stomp`: SO-101 5축에 맞춘 40 waypoint 최적화 설정

SO-101 팔은 5-DOF이므로 `arm` 그룹은 `position_only_ik: true`입니다. 완전한 6축
orientation 추종은 불가능하며, 조인트 목표 또는 위치 목표를 먼저 사용하는 것이
안정적입니다. Pilz `LIN`/`CIRC` 역시 시작 자세와 목표 자세의 방향 제약이 5-DOF
가용 범위 안에 있어야 합니다.

## 컨트롤러 토픽과 간단한 확인

```bash
ros2 topic pub --once /arm_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll], points: [{positions: [0.0, -0.7, 1.0, -0.3, 0.0], time_from_start: {sec: 3}}]}"
```

MoveIt은 다음 FollowJointTrajectory action으로 실행합니다.

- `/arm_controller/follow_joint_trajectory`
- `/gripper_controller/follow_joint_trajectory`

## 주요 설정 파일

`build/`와 `install/`은 생성물이므로 직접 수정하지 않고 항상 `src/` 아래 파일을
수정합니다.

| 변경 대상 | 파일 |
|---|---|
| 링크 구조, joint origin/axis, mesh, URDF limit | `src/so101_description/urdf/so101_model.urdf.xacro` |
| `ros2_control` joint limit, 초기값, hardware plugin | `src/so101_description/urdf/so101.urdf.xacro` |
| controller joint, update/publish rate, constraint | `src/so101_bringup/config/controllers.yaml` |
| Gazebo 조명, 바닥, 물리 및 환경 모델 | `src/so101_bringup/worlds/empty.sdf` |
| MoveIt group, named pose, collision matrix | `src/so101_moveit_config/config/so101.srdf` |
| MoveIt joint 속도·가속도 제한 | `src/so101_moveit_config/config/joint_limits.yaml` |
| 위치 우선 KDL IK | `src/so101_moveit_config/config/kinematics.yaml` |
| OMPL planner | `src/so101_moveit_config/config/ompl_planning.yaml` |
| Pilz Cartesian limit | `src/so101_moveit_config/config/pilz_cartesian_limits.yaml` |
| STOMP rollout/iteration/cost | `src/so101_moveit_config/config/stomp_planning.yaml` |

물리 관절 범위를 변경할 때는 모델 URDF의 `<limit>`과 `so101.urdf.xacro`의
`ros2_control` lower/upper를 함께 변경합니다. 실제 로봇에 처음 적용할 때는
`joint_limits.yaml`의 속도와 가속도를 낮춘 상태에서 검증합니다.

설정 변경 후 필요한 패키지만 다시 빌드할 수 있습니다.

```bash
colcon build --symlink-install --packages-select \
  so101_description so101_bringup so101_moveit_config
source install/setup.bash
```

## 실제 LeRobot 하드웨어 연동 시 주의

실제 드라이버는 gripper의 LeRobot 범위와 URDF radian 범위를 변환하며, body joint는
4095 tick/회전과 각 장치의 캘리브레이션 midpoint를 사용합니다. 현재 검증에서 follower
2번 `shoulder_lift`가 `Overload error` 상태를 보고했으므로, 전원을 껐다 켜고 관절의
물리적 걸림과 배선을 확인한 뒤 토크를 활성화해야 합니다.

## 출처 및 호환성

- SO-101 CAD/URDF: https://github.com/TheRobotStudio/SO-ARM100
- Humble + Harmonic: https://gazebosim.org/docs/harmonic/ros_installation/
- gz_ros2_control: https://control.ros.org/humble/doc/gz_ros2_control/doc/index.html
- MoveIt Humble: https://moveit.picknik.ai/humble/

가져온 SO-101 자산은 `so101_description/LICENSE`의 Apache-2.0 조건을 따릅니다.
