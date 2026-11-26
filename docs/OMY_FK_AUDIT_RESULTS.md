# OMY FK·위치·속도 정합 감사 결과 (2026-11-27)

**판정: PASS.** 45개 시퀀스(11,999프레임) 전체에서 측정 관절값 FK로 만든 로봇 링크·표면점·속도가 시뮬레이터 링크 GT와 일치했다. 최대 오차는 위치 0.00087mm, 회전 0.00012°, 표면점 속도 0.000029m/s이며, 사전 조사 기준(위치 p95 1mm, 회전 p95 0.5°, 속도 p95 0.02m/s)보다 약 1,000~5,000배 작다. hard fail(시간 불일치, 단위 오류, 비유한 값)은 0건이다. 학습에 쓰는 temporal cache도 이 경로로 다시 계산한 값과 비트 단위로 같았다(최대 차이 0.0).

- 실행: `scripts/audit_omy_fk.py`, 코드 commit `8f64440`(clean), 2026-11-27.
- 전체 산출물(로컬): `outputs/omy_validation_5080_004/fk_audit/` — `summary.json`, `per_frame.csv`(sha256 `e6370b26…`), `per_link.csv`(sha256 `d04a7c56…`), `overlays/` 12장.
- 저장소 사본: [`docs/results/omy_validation_5080_004/fk_audit/`](results/omy_validation_5080_004/fk_audit/) — `summary.json`, overlay 3장.

## 무엇을 무엇과 비교했나

| 구분 | 내용 |
| --- | --- |
| 검사 대상(모델 입력 경로) | `robot_observations.jsonl` + `previous_robot_state.json` + `robot/joint_inventory.json` → `omy_kinematics.forward_kinematics` → `OmySequence._surface_pair` → `point_features`. 학습 cache와 rollout이 실제로 쓰는 코드 그대로다. |
| 독립 기준 | `frames.jsonl`의 `T_world_robot_links`(시뮬레이터가 저장한 링크 11개 pose, `pose_convention: T_world_link_origin`). 이 감사에서만 읽고 모델 입력에는 넣지 않는다. |
| 링크 | world, link1–6, 그리퍼 4개(rh_p12_rn_l1/l2/r1/r2). FK가 만드는 링크와 표면점을 뽑는 링크가 11개로 같다. |
| 표면점 | 각 링크 mesh의 고정 canonical 점(총 512개)을 FK pose와 GT pose로 **각각** 변환해 비교한다. 같은 FK로 양쪽 기준을 만들지 않았다. |
| 속도 | FK 경로: (현재점 − 이전점)/dt, 두 시점 모두 **현재 카메라 좌표계**. GT: 같은 점을 GT 링크 pose 두 시점으로 옮겨 같은 방식으로 계산한다. 실제 timestamp 차이로 나눈 구간 평균 속도다. |
| 정규화 입력 | `point_features` 출력(가설 = 그 프레임의 GT 물체 pose)을 numpy로 따로 계산한 기대값과 비교했다. 로봇 xyz/diameter와 속도/diameter, CAD 행(위치 = CAD/diameter, 플래그·속도 0)을 확인한다. |

데이터 팀의 `validation/all_link_fk.json`은 parent capture의 `diagnostics.json`과 별도 inventory를 쓴 검사였다. 이번 감사는 export된 시퀀스 파일과 학습 코드 경로를 직접 검사한 것이므로 그 결과를 대체하거나 재사용하지 않았다.

## 결과 (45개 시퀀스 전체)

| 항목 | 표본 수 | 평균 | 중앙값 | p95 | 최대 | 최악 위치 |
| --- | --- | --- | --- | --- | --- | --- |
| 링크 위치 오차 (mm) | 131,989 | 0.00014 | 0.00013 | 0.00034 | 0.00087 | asymmetric_A_04 f36, rh_p12_rn_r2 |
| 링크 회전 오차 (deg) | 131,989 | 0.000030 | 0.000028 | 0.000063 | 0.00012 | box_A_01 f50, link6 |
| 동일 표면점 거리 (mm) | 6,143,488 | 0.00015 | 0.00014 | 0.00035 | 0.00094 | asymmetric_A_04 f36 |
| 표면점 속도 차 (m/s) | 6,120,448 | 0.0000044 | 0.0000039 | 0.000010 | 0.000029 | asymmetric_C_04 f232 |
| 정규화 xyz 차 (mm 환산) | 11,999 프레임 | 0.00032 | 0.00030 | 0.00050 | 0.00085 | — |
| 정규화 속도 차 (m/s 환산) | 11,954 프레임 | 0.0000095 | 0.0000090 | 0.000015 | 0.000029 | — |
| 참고: GT 표면점 속력 (m/s) | 6,120,448 | 0.030 | 0.017 | 0.091 | 0.53 | — |

오차 크기는 float32 저장 정밀도(1–2m 좌표에서 약 0.1–0.2µm)와 같은 수준이다. 실제 속력(p95 0.09m/s)에 비해 속도 차는 약 0.01%다.

## 형식·시간·단위 검사

| 검사 | 결과 |
| --- | --- |
| frame_id 정렬 (observations ↔ frames), 연속성 | 45/45 일치, 누락 0 |
| timestamp 차이 (두 파일) | 최대 0.0s |
| dt | 모든 프레임 1/30s (최소 0.0333333333333332, 최대 0.0333333333333350), previous_state 포함 |
| 관절 이름 | inventory의 가동 관절 10개와 정확히 같다 (root_joint 제외) |
| 관절 단위 | radian. inventory 한계(도 단위)를 rad로 바꿔 비교했을 때 최대 초과 2.7e-6 rad (허용 1e-3) |
| T_world_camera / T_world_robot_base | 두 파일 간 차이 0.0 |
| 강체 변환 유효성 | 최대 오차 2.7e-15 |
| 비유한 값 | 0 |
| 시간 지연 진단 | FK(i)와 GT(i)의 평균 표면 오차 0.00016mm vs GT(i−1) 1.01mm, GT(i+1) 1.01mm → 지연 없음 |
| 체계적 편향 | 링크별 평균 부호 오차 최대 0.00027mm (카메라 좌표) → 축·시간 편향 없음 |
| cache 재계산 | motion-train 193/1925, motion-validation 48/478 샘플(10개마다 1개): 저장된 point feature·target과 차이 0.0 |

## 회귀 테스트 (합성)

`tests/test_fk_audit.py`는 `omy_kinematics`를 쓰지 않고 직접 합성한 2관절 기준 체인과 비교한다. 비단위 회전(30°)을 넣어 quaternion 순서까지 검사한다.

| 상황 | 기대 동작 | 결과 |
| --- | --- | --- |
| 정상 FK | 기준 체인과 일치, 조사 플래그 없음 | 통과 |
| 정지 로봇 + 카메라 이동 | 가짜 속도 0 (두 시점 모두 현재 카메라 좌표) | 통과 |
| 관절 회전 + base 이동 | 속도가 기준과 일치, 0이 아님 | 통과 |
| 관절값을 degree로 넣음 | 플래그 | 통과 |
| 관절 부호 반전 | 플래그 | 통과 |
| 한 프레임 지연 | 플래그, 지연 진단이 이전 프레임을 지목 | 통과 |
| dt 단위 오류 (ms) | 속도 플래그 | 통과 |

## 확인하지 못한 것

- 시뮬레이터 링크 선속도·각속도는 export에 없다. 속도는 GT pose 구간 차분으로만 비교했다(v + ω×r 보조 비교 불가). 필요하면 export에 링크별 `linear_velocity`, `angular_velocity`와 기준점·좌표계 정의를 추가해야 한다.
- `previous_robot_state.json`에는 시뮬레이터 링크 pose가 없다. 그래서 각 시퀀스 frame 0의 속도(45프레임)는 독립 기준이 없어 비교에서 뺐다. 위치는 frame 0도 비교했다.
- 이 감사는 시뮬레이터 안의 정합성이다. 실제 로봇의 관절 encoder 노이즈나 calibration 오차는 포함하지 않는다. FK–GT 차이가 수치 정밀도 수준이므로 이 export의 관측 관절값에는 별도 노이즈가 들어 있지 않은 것으로 보인다(노이즈 주입 여부는 export 설정에서 확인하지 않았다).

## 조치

수정할 것이 없다. 기존 temporal cache(`outputs/omy_training_5080_003/motion-*`, manifest sha256 train `cb18c1f5…`, validation `9539d143…`)를 CAD-only 대조 학습에 그대로 사용했다.

## 재현

```bash
conda activate rafp
python scripts/audit_omy_fk.py \
  --dataset ~/mj-projects/omy-tracking-dataset/outputs/omy_pilot/dataset \
  --output outputs/omy_validation_5080_004/fk_audit \
  --cache outputs/omy_training_5080_003/motion-train \
  --cache outputs/omy_training_5080_003/motion-validation --cache-stride 10
python -m pytest -q tests/test_fk_audit.py
```
