# SO-101 calibration

`so101_leader.json`은 Maker Faire 2026 텔레오퍼레이션에 사용하는 리더암
`so101_leader`의 LeRobot 캘리브레이션 백업입니다.

이 값은 해당 리더암의 조립 위치와 STS3215 encoder에 종속됩니다. 다른 리더암에
그대로 사용하지 말고, 모터나 horn을 교체하거나 조립 각도를 변경한 경우에는 다시
캘리브레이션합니다.

## LeRobot 캐시로 복원

저장소 루트에서 실행합니다.

```bash
mkdir -p ~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader
cp calibration/so101_leader.json \
  ~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/so101_leader.json
```

텔레오퍼레이션과 기록 명령에서는 캘리브레이션 때 사용한 것과 동일한 ID를
지정합니다.

```text
--teleop.id=so101_leader
```
