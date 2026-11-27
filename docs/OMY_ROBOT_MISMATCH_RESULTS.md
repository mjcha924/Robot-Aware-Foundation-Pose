# OMY 로봇 상태 불일치 대조 · 첫 프레임 등록 초기화 · 보조 지표 (2026-11-27)

[CAD-only 대조](OMY_CAD_ABLATION_RESULTS.md)의 후속이다. 004 checkpoint를 다시 학습하지 않고 그대로 썼다. 비교 조건과 seed(42/43/44)도 같다. 9개 validation 시퀀스를 checkpoint 선택과 평가에 함께 쓴 결과이고, 독립 test 성능이 아니다.

## 결론

1. **부분 가림(cylinder_A_04)에서 geometry의 개선은 정확한 로봇 상태로 거의 설명되지 않는다.** 추론 때 로봇 입력만 망가뜨려 봤다. 다른 시퀀스의 로봇 넣기, 첫 프레임에 고정, 0.5초 지연, 관절 노이즈 0.02rad의 네 가지다. 그래도 cylinder_A_04 오차는 1.45 → 1.44–1.80mm였다. geometry와 cad-only 사이 차이 중 사라진 비율은 최대 10%다(seed별 최대). 다른 시퀀스의 로봇을 넣으면 물체 근처 로봇 점이 평균 114mm 다른 곳으로 옮겨지는데도 그랬다.
2. **그렇다고 로봇 점이 필요 없는 것은 아니다(결과를 보고 추가한 대조).** 같은 geometry checkpoint에서 로봇 점을 아예 빼고 CAD 점만 넣으면 cylinder_A_04가 6.26mm [3.57–11.60]로 나빠진다. 사라진 차이 비율은 0.26 / 0.66 / 2.97이다. 분기를 통째로 끄면 6.43mm [3.99–10.28]다. 즉 이 모델은 **로봇 모양의 점이 있다는 사실**에 의존한다. 그 점의 위치가 정확한지에는 거의 민감하지 않다.
3. **부분 가림에서 geometry가 앞선 내용은 위치가 아니라 마커 긴 축 회전이다(보조 분석).** cylinder_A_04의 평균 위치 오차는 모든 학습 모델이 0.95–1.03mm로 같다. 평균 회전 오차는 geometry 4.8°, cad-only 56.9°, visual-ft 39.8°다. 사용자 확인에 따라 회전은 이 과제에서 중요하다. 그래서 이 차이는 실제 개선으로 보고, 대칭 지표로 지우지 않는다.
4. **FoundationPose 등록으로 시작해도(pose GT 없음) 결론이 같다.** 첫 프레임 등록 오차는 9개 모두 지름의 10% 미만이었다(표면 0.7–8.2mm). 추적 결과는 다음과 같다.
   - 전체: geometry 2.22mm [1.98–2.70], kinematic-refine 3.24, visual 3.38, cad-only 5.34, visual-ft 6.75
   - cylinder_A_04: geometry가 3/3 seed에서 가장 좋다.
   - 다만 등록에 데이터셋의 oracle visible mask를 썼다. pose 정답은 쓰지 않았지만, 분할(segmentation) 정답은 썼다.
5. **완전 가림(cylinder_C_04)은 이번에도 판별할 수 없다.** 오염 종류에 따라 오차가 오르기도 내리기도 한다(9.2–47.3mm). 놓침은 freeze-first와 joint-noise-0.02에서 각 1/3, drop-robot-rows에서 1/3이다. 등록 초기화에서는 cad-only s43이 다시 유일하게 회전까지 되찾았다(마지막 0.27mm).
6. **zero-velocity는 효과가 정확히 0이었다. geometry 모드가 원래 속도 채널을 0으로 지우기 때문이다.** 실험 전에 걸러냈어야 했는데 놓쳤다. 결과적으로 새 코드가 기존 경로를 바꾸지 않았다는 확인 용도가 됐다. 오염 없이 다시 돌린 결과도 004와 정확히 같다(차이 0.0).

### 사전 판정 규칙 적용 (plan.json, 실행 전에 작성)

| 규칙 | 결과 | 판정 |
| --- | --- | --- |
| 큰 오염(swap-sequence, freeze-first, delay-15)이 cylinder_A_04 차이의 절반 이상을 3/3 seed에서 없애면 "로봇 상태를 쓴다" | 최대 0.20(s42 freeze-first). 나머지는 0.10 이하 | **충족 안 함** |
| 모든 오염·seed에서 cylinder_A_04 변화가 0.3mm 미만이면 "로봇 상태 값으로 설명 안 됨" | freeze-first s42 +0.63mm, swap-sequence +0.16 / +0.52 / +0.35mm(s42/43/44)로 일부가 0.3mm를 넘음 | **엄밀히는 충족 안 함**. 작은 의존은 있다 |

두 규칙 모두 충족하지 못했다. 정리하면 **로봇 상태에 대한 의존은 작다**. 개선의 대부분은 로봇 점이 있다는 사실(drop-robot·bypass 대조)과 연결된다. 다만 이 두 대조는 결과를 본 뒤 추가한 것이다.

### 이전 보고서에서 고칠 해석

[CAD-only 보고서](OMY_CAD_ABLATION_RESULTS.md)의 결론 1은 "부분 가림에 대한 로봇 정보의 추가 기여"라고 썼다. 이번 결과로 보면 더 정확한 표현은 이렇다. "로봇 점 분기를 함께 학습한 모델이 부분 가림 중 긴 축 회전 drift를 막는다. 이 효과는 로봇 상태가 정확한지에 거의 의존하지 않는다." 무엇이 이 효과를 만드는지는 아직 모른다. 로봇 점의 수(768 vs 256), 로봇 형상의 분포, 학습 중 정규화 효과 등을 구분하지 못했다.

## 1. 로봇 상태 불일치 대조

### 조건

- 모델: `outputs/omy_validation_5080_004/training/temporal-geometry-s{42,43,44}/best.pt` (sha256은 004와 같음을 스크립트가 확인)
- 초기화: oracle-first-frame (004와 같은 initial pose 파일)
- 바꾸는 것: refiner에 들어가는 로봇 관절값과 로봇 base pose만. 카메라 pose, 이미지, timestamp, GT, 채점은 그대로다(`src/robot_conditioned_pose/robot_perturbation.py`).
- 코드: 오염 실험 `1fd56fb`(clean), 결과를 보고 추가한 두 대조 `729b158`(clean)

| 조건 | 내용 | cylinder_A_04 물체 근처 로봇 점 이동 (mm, 평균/최대) |
| --- | --- | --- |
| none | 오염 없음, 같은 코드로 재실행 | 0 |
| delay-3 / delay-15 | 3 / 15프레임 전(100 / 500ms) 로봇 상태 | 3.0/8.9 · 15.0/43.3 |
| zero-velocity | 이전 상태 = 현재 상태 (**geometry는 속도를 안 써서 효과 없음**) | 0 |
| freeze-first | 모든 프레임에 frame 0 로봇 상태 | 60.1/120.2 |
| swap-sequence | 다음 validation 시퀀스(정렬 순, 순환)의 로봇 상태 | 114.0/161.0 |
| joint-noise-0.002 / 0.02 | 관절마다, 프레임마다 독립 가우시안(rad, seed 2026) | 1.4/3.8 · 14.1/38.7 |
| drop-robot-rows (결과 보고 추가) | 로봇 행을 빼고 CAD 256행만 입력 | — |
| bypass-branch (결과 보고 추가) | 점 분기를 건너뜀(시각 token만) | — |

cylinder_A_04에서 물체 중심과 가장 가까운 로봇 점 64개까지의 평균 거리는 168mm다. 즉 이 시퀀스에서 로봇은 물체에 닿지 않는다.

### 결과 (seed 평균 [범위], mm. 사라진 차이 비율 = (오염 − none) / (cad-only − none), seed별로 짝지어 계산)

| 조건 | 전체 9개 | 쉬운 7개 | cylinder_A_04 | A_04 사라진 차이 비율 | cylinder_C_04 | 놓침 |
| --- | --- | --- | --- | --- | --- | --- |
| none | 2.34 [2.01–2.66] | 1.02 | 1.45 [1.27–1.63] | 0 | 12.45 [9.41–15.50] | 0/27 |
| delay-3 | 2.27 [1.99–2.80] | 1.02 | 1.45 [1.30–1.61] | 0.00 | 11.87 [9.23–16.60] | 0/27 |
| delay-15 | 2.13 [2.03–2.21] | 1.04 | 1.47 [1.29–1.63] | 0.00 [0.00–0.01] | 10.42 [9.64–11.22] | 0/27 |
| zero-velocity | 2.34 [2.01–2.66] | 1.02 | 1.45 [1.27–1.63] | 0 | 12.45 [9.41–15.50] | 0/27 |
| freeze-first | 3.58 [2.22–6.28] | 1.12 | 1.65 [1.31–2.08] | 0.06 [−0.02–0.20] | 22.75 [10.46–47.26] | 1/27 |
| swap-sequence | 2.60 [2.43–2.70] | 1.18 | 1.80 [1.61–1.98] | 0.07 [0.05–0.10] | 13.29 [11.54–14.39] | 0/27 |
| joint-noise-0.002 | 2.32 [1.98–2.68] | 1.02 | 1.44 [1.26–1.63] | 0.00 | 12.30 [9.16–15.68] | 0/27 |
| joint-noise-0.02 | 3.28 [2.11–5.42] | 1.02 | 1.47 [1.32–1.66] | 0.00 [0.00–0.01] | 20.89 [10.41–40.29] | 1/27 |
| drop-robot-rows | 4.47 [2.92–6.17] | 1.85 | 6.26 [3.57–11.60] | 1.30 [0.26–2.97] | 21.00 [11.05–39.42] | 1/27 |
| bypass-branch | 3.07 [2.67–3.35] | 1.43 | 6.43 [3.99–10.28] | 1.28 [0.43–2.71] | 11.20 [9.87–13.33] | 0/27 |
| 참고: cad-only (004) | 4.27 [2.85–6.69] | 1.00 | 6.59 [4.70–10.07] | 1 | 24.81 [8.63–47.93] | 1/3 |

- 놓침은 마지막 오차가 50mm를 넘은 run의 수다.
- seed별 전체 표는 [`mismatch_tables.md`](results/omy_validation_5080_005/mismatch/mismatch_tables.md)에 있다.
- 사라진 차이 비율이 1을 넘으면 cad-only보다도 나쁘다는 뜻이다.

읽는 법:
- 로봇 상태 값을 틀리게 넣는 대조(delay, swap, freeze, noise)는 부분 가림 개선을 거의 없애지 못한다.
- 로봇 점을 없애거나 분기를 끄는 대조는 개선을 대부분 또는 전부 없앤다.
- 쉬운 7개도 drop-robot-rows와 bypass-branch에서만 나빠진다(1.02 → 1.85 / 1.43). 학습된 모델이 로봇 점의 존재를 전제로 맞춰져 있다는 뜻이다.

## 2. 첫 프레임 등록 초기화 (pose GT 없음)

### 조건

- `scripts/prepare_registered_initial_poses.py`: upstream `FoundationPose.register`를 frame 0에 한 번씩 실행했다.
  - 입력: RGB-D, K, CAD mesh, 데이터셋 frame-0 object mask
  - 설정: 5 iteration, seed 0
  - 재시도와 선택은 하지 않았다.
- **mask는 데이터셋의 oracle visible mask다** (manifest protocol `oracle_visible_mask_for_equal_method_comparison`). 그래서 이 조건의 이름은 "pose oracle 없음, segmentation oracle 있음"이다.
- upstream의 C++ 확장 `mycpp`는 이 PC에서 빌드되어 있지 않다(Eigen/Boost/pybind11 없음). 그래서 회전 격자 중복 제거 함수 `cluster_poses`를 한 줄씩 Python으로 옮겼다(`src/robot_conditioned_pose/mycpp_port.py`, 테스트 포함). 원본 C++과 직접 비교한 실행은 없다.
- 첫 시도는 `mycpp`가 없어 실패했다. 그 빈 폴더(`initial-registered/`)는 지우지 않고 그대로 두었다. 사용한 결과는 `initial-registered-v2/`다.
- 그 밖의 설정(iteration 2, checkpoint, 평가)은 004와 같다. 등록 pose 하나를 모든 방법과 seed가 함께 쓴다.

### 첫 프레임 등록 오차 (모든 pose를 저장한 뒤 보고용으로만 계산)

| 시퀀스 | 표면 오차 (mm) | 위치 (mm) | 회전 (°) |
| --- | --- | --- | --- |
| asymmetric_A_04 | 0.73 | 0.40 | 0.90 |
| asymmetric_B_04 | 0.72 | 0.29 | 0.79 |
| asymmetric_C_04 | 8.19 | 7.39 | 16.36 |
| box_A_04 / B / C | 1.19 / 1.18 / 1.39 | 1.14 / 1.14 / 1.14 | 0.58 / 0.55 / 1.63 |
| cylinder_A_04 / B / C | 1.47 / 1.37 / 2.38 | 1.09 / 0.93 / 1.64 | 6.15 / 5.48 / 3.73 |

### 추적 결과 (seed 평균 [범위], mm)

| 방법 | 전체 9개 | p95 | 쉬운 7개 | cylinder_A_04 | cylinder_C_04 | 놓침 |
| --- | --- | --- | --- | --- | --- | --- |
| visual (사전학습) | 3.38 | 8.52 | 2.11 | 3.44 | 12.23 | 0/3 |
| kinematic-refine | 3.24 | 8.46 | 2.12 | 3.41 | 10.95 | 0/3 |
| visual-ft | 6.75 [6.69–6.82] | 26.01 | 1.00 | 5.06 | 48.74 | 3/3 |
| cad-only | 5.34 [2.85–7.17] | 19.28 | 1.00 | 8.31 [4.82–10.17] | 32.77 [8.59–47.34] | 2/3 |
| geometry | **2.22** [1.98–2.70] | **5.58** | 1.02 | **1.43** [1.24–1.62] | 11.48 [9.24–15.92] | **0/3** |

- 결정적 baseline(visual, kinematic-refine)은 seed마다 같은 결과를 다시 돌린 것이라 독립 반복이 아니다.
- 짝지은 차이는 [`registered/summary_tables.md`](results/omy_validation_5080_005/registered/summary_tables.md)에 있다.
- 등록으로 시작해도 oracle 시작(004)과 거의 같은 값이 나온다. 첫 프레임 오차가 지름의 10% 미만이면 이 checkpoint들의 추적 결과는 초기화에 크게 민감하지 않다.
- asymmetric_C_04는 첫 프레임 오차가 8.2mm로 가장 컸는데도, geometry가 1.1mm 수준으로 바로 따라붙었다.

## 3. 보조 지표: ADD-S와 위치·회전 분해

**보조 기록이다. 기준 지표를 바꾸지 않는다.** 사용자가 마커 회전이 중요하다고 확인했으므로, 회전을 무시하는 ADD-S는 실패를 가릴 수 있다. ADD-S는 각 예측 표면점에서 가장 가까운 GT 표면점까지 거리의 평균이다(4096점, 기준 지표와 같은 표본).

| 실험 · 방법 | 기준 지표 전체 | ADD-S 전체 | A_04 기준 | A_04 ADD-S | A_04 평균 회전 (°) | C_04 마지막 ADD-S | C_04 마지막 회전 (°) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| oracle · geometry | 2.34 | 1.15 | 1.45 | 0.93 | 4.8 | 0.92 | 142 [88–173] |
| oracle · cad-only | 4.27 | 2.15 | 6.59 | 1.00 | 56.9 | 49.55 | 69 [0.8–174] |
| oracle · visual-ft | 6.76 | 4.04 | 5.09 | 1.01 | 39.8 | 148.38 | 96 |
| oracle · kinematic-refine | 3.23 | 1.70 | 3.40 | 1.71 | 11.5 | 0.98 | 91 |
| 등록 · geometry | 2.22 | 1.13 | 1.43 | 0.92 | 4.7 | 0.94 | 113 [85–165] |
| 등록 · cad-only | 5.34 | 2.84 | 8.31 | 1.02 | 75.1 | 96.04 | 58 |

- cylinder_A_04에서 학습 모델 셋의 ADD-S는 0.92–1.02mm로 같다. 차이는 거의 전부 긴 축 회전이다.
- cylinder_C_04에서 놓치지 않은 run은 마지막 ADD-S가 약 1mm다. 그러나 회전은 85–175° 틀려 있다. 회전이 중요하므로 이 run들은 **회복하지 못한 것**으로 본다.
- 전체 값: [`supplementary_groups.csv`](results/omy_validation_5080_005/supplementary/supplementary_groups.csv), run별 값: `per_run_004.csv`, `per_run_005.csv`.

## 미완료·한계

- **cad-only-768 / 용량 대조를 이제는 해야 한다.** 이번 결과로 "로봇 점의 존재"가 핵심 후보가 됐다. 정확한 상태는 거의 상관없었기 때문이다. 이것이 점 수(768 vs 256) 때문인지, 로봇 같은 형상 분포 때문인지 구분하려면 학습이 필요한 대조가 남아 있다. 예를 들어 CAD 768점, 로봇 점을 무작위 위치에 둔 학습, 로봇 상태를 섞어서 하는 학습이 있다.
- drop-robot-rows와 bypass-branch는 결과를 본 뒤 추가했다. 게다가 학습 때 본 적 없는 입력이라(분포 밖 입력), 성능 하락이 "로봇 정보가 필요해서"인지 "입력 분포가 바뀌어서"인지 분리할 수 없다.
- zero-velocity는 geometry에서 효과가 없는 조건이었다. 속도를 쓰는 motion 모드 checkpoint는 이번에 시험하지 않았다.
- 등록 초기화도 oracle mask를 쓴다. mask까지 추정하는 완전한 실사용 파이프라인은 아니다. `mycpp` Python 포팅은 원본 C++과 직접 비교하지 못했다.
- 완전 가림 사건은 validation에 하나뿐이고 독립 test가 없다. 모든 결과는 시뮬레이터 데이터다.

## 재현

```bash
conda activate rafp
R=outputs/omy_validation_5080_005
bash $R/run_all.sh        # 오염 216회 + 등록 시작 135회 (code 1fd56fb)
bash $R/run_posthoc.sh    # drop-robot-rows / bypass-branch 54회 (code 729b158)
python scripts/summarize_robot_mismatch.py --mismatch $R/mismatch --reference-evaluation outputs/omy_validation_5080_004/evaluation --output $R/analysis/mismatch
python scripts/summarize_cad_ablation.py --training outputs/omy_validation_5080_004/training --evaluation $R/registered \
  --reference outputs/omy_training_5080_003/pretrained_reference_motion.json --output $R/analysis/registered
python scripts/score_supplementary_metrics.py --dataset <dataset> --root $R/registered --root $R/mismatch --output $R/supplementary-005
python scripts/measure_perturbation_magnitude.py --dataset <dataset> --donors $R/mismatch/donors.json --output $R/analysis/perturbation_magnitude.csv
```

등록 pose는 `prepare_registered_initial_poses.py`로 만들었다. 코드 커밋 전 작업 트리에서 실행했지만, 이 스크립트 내용은 `1fd56fb`의 파일과 같다. 원본 pose는 [`initial-registered/`](results/omy_validation_5080_005/initial-registered/)에 함께 올렸다.
