# Maker Faire 2026 SO-101 Teleoperation

LeRobot SO-101 기반 마스터-슬레이브 텔레오퍼레이션 프로젝트입니다. 기존 소개용
GitHub Pages와 함께, ROS 2 Humble에서 SO-101을 시뮬레이션하고 모션 플래닝할 수 있는
워크스페이스를 포함합니다.

## 포함 기능

- SO-101 URDF/Xacro 및 STL mesh
- RViz 모델 확인
- Gazebo Harmonic 시뮬레이션
- `ros2_control` 팔/그리퍼 trajectory controller
- MoveIt 2 및 위치 우선 KDL IK
- OMPL / Pilz / STOMP planning pipeline
- Gazebo + MoveIt + RViz 통합 launch

## 저장소 구조

```text
.
├── index.html, styles.css, script.js  # 프로젝트 소개 웹사이트
├── assets/                            # 웹사이트 이미지
├── calibration/                       # 장치별 LeRobot 캘리브레이션 백업
└── ros2_ws/                           # SO-101 ROS 2 워크스페이스
    ├── src/
    │   ├── so101_description/
    │   ├── so101_bringup/
    │   ├── so101_moveit_config/
    │   ├── gz_ros2_control/
    │   └── stomp_moveit/
    └── README.md                      # 설치·빌드·실행·설정 안내
```

## 빠른 실행

의존성 설치 등 전체 과정은 [`ros2_ws/README.md`](ros2_ws/README.md)를 확인하세요.

```bash
cd ros2_ws
source /opt/ros/humble/setup.bash
export GZ_VERSION=harmonic

colcon build --symlink-install \
  --packages-up-to so101_moveit_config \
  --cmake-args -DBUILD_TESTING=OFF -DBUILD_STOMP_EXAMPLE=OFF

source install/setup.bash
ros2 launch so101_bringup sim_moveit.launch.py
```

검증 환경은 Ubuntu 22.04, ROS 2 Humble, Gazebo Harmonic 8.15입니다.

리더암 캘리브레이션 백업과 복원 방법은
[`calibration/README.md`](calibration/README.md)에 있습니다.

> 현재 `mock`과 Gazebo용 `ros2_control` 구성을 제공합니다. 실제 STS3215 서보를
> 구동하려면 calibration 및 단위 변환을 포함한 별도 hardware interface가 필요합니다.
