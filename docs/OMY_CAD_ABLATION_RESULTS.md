# OMY temporal CAD-only 대조 결과 (2026-11-27)

같은 temporal cache·설정·seed(42/43/44)로 visual / cad-only / geometry(로봇+CAD)를 새로 학습하고, 같은 코드 commit에서 matched rollout으로 비교했다. 모든 추적 수치는 **첫 프레임 GT 초기화(oracle-first-frame)** 조건이고 9개 validation 시퀀스를 학습 선택(best.pt)과 평가에 함께 쓴 결과다. 실사용 초기화나 독립 test 성능이 아니다.

> **후속 결과로 해석 수정 (2026-11-27, [OMY_ROBOT_MISMATCH_RESULTS.md](OMY_ROBOT_MISMATCH_RESULTS.md)):** 아래 결론 1의 "로봇 정보의 추가 기여"는 너무 강한 표현이다. 추론 때 로봇 상태를 틀리게 넣어도(다른 시퀀스의 로봇, 첫 프레임 고정, 지연, 노이즈) cylinder_A_04의 개선은 거의 그대로 남았다(사라진 차이 비율 최대 0.20). 로봇 점을 아예 빼면 개선이 사라졌다. 또 cylinder_A_04에서 앞선 내용은 위치가 아니라 긴 축 회전이다(평균 회전 오차 geometry 4.8°, cad-only 56.9°, visual-ft 39.8°, 위치 오차는 모두 약 1mm). 아래 본문의 수치는 바뀌지 않았다.

## 결론

1. **부분 가림에서는 로봇 정보의 추가 기여가 3/3 seed에서 분명하다.** cylinder_A_04(가시 16–50%) 평균 오차는 geometry 1.27–1.63mm, cad-only 4.70–10.07mm, visual-ft 5.03–5.16mm다. CAD-only는 visual-ft와 같은 수준이라, 이 개선은 기하 분기를 붙인 효과나 물체 형상 조건화로 설명되지 않는다.
2. **전체 macro 평균도 geometry가 cad-only보다 3/3 seed에서 낮다(차이 −0.93 / −0.19 / −4.68mm).** 다만 쉬운 7개 시퀀스에서는 두 모델이 같다(차이 ±0.04mm). 차이는 가림 시퀀스에서만 생긴다.
3. **완전 가림(cylinder_C_04)에서는 seed마다 순위가 바뀌어 판별이 불충분하다.** 물체를 놓친 run(마지막 오차 > 50mm)은 geometry 0/3, cad-only 1/3, visual-ft 3/3이다. 평균 오차 차이(geometry − cad-only)는 −5.43 / +6.88 / −38.53mm로 부호가 바뀐다. 이 시퀀스 하나에서 가장 좋은 단일 run은 cad-only s43이었다(마지막 0.3mm, 회전 0.8°). 이번 실험 전체에서 완전 가림 후 원래 자세까지 되찾은 유일한 run이다.
4. **CAD-only는 visual-ft보다 덜 끌려가지만 부분 가림 정확도는 개선하지 못했다.** macro 차이(cad-only − visual-ft)는 −3.43 / −3.96 / −0.07mm, cylinder_C_04 놓침은 1/3 vs 3/3이다. cylinder_A_04는 −0.33 / +4.91 / −0.07mm로 개선이 없다.
5. **보충 분석: 완전 가림 후 남는 12–17mm 오차는 위치가 아니라 마커 긴 축 회전이다.** 물체를 놓치지 않은 run은 마지막 위치 오차가 0.1–1.1mm다. 남은 surface 오차는 긴 축(mesh y축) 둘레 87–175° 회전에서 나온다. 이 물체는 거의 원통이고 manifest에 대칭이 선언되어 있지 않아, 이 회전이 그대로 오차로 잡힌다. 이 분석은 사전에 정하지 않았고, 기존 결과를 보고 추가했다.
6. **geometry의 0.1 diameter 초과 프레임 비율(4.1–5.6%)이 kinematic-refine(3.3%)보다 높은 이유는 전부 cylinder_C_04다.** 다른 8개 시퀀스는 모든 방법이 0%다. cylinder_C_04에서 geometry는 재등장 후 16.8mm(회전 약 170°)에 머물러 기준 12.1mm를 넘는다. kinematic-refine은 12.1mm(회전 약 90°)로 기준선 바로 근처에 머문다.
7. **one-step validation은 이번에도 추적 결과를 구분하지 못했다.** 세 모드의 best val은 3.52–3.69mm로 거의 같다.

### 사전 판정 규칙 적용

| 관찰 | 해당 여부 | 해석 |
| --- | --- | --- |
| Robot+CAD가 CAD-only보다 여러 seed·시퀀스에서 개선 | 부분 가림 cylinder_A_04: 3/3 seed. macro: 3/3 seed. 쉬운 7개: 차이 없음 | 이 설정에서 **부분 가림에 대한 로봇 입력의 추가 기여를 지지** |
| 평균은 비슷하고 가림 이탈만 감소 | 쉬운 시퀀스는 같고 차이는 가림에서만 생김 | 정확도보다 **가림 상황의 안정성**에 기여할 가능성 |
| seed별 순위가 바뀜 | cylinder_C_04(완전 가림) | 완전 가림·재등장 회복은 **현재 데이터로 판별 불충분** |
| CAD-only도 악화 | visual-ft 대비 macro 비슷하거나 개선, 부분 가림은 비슷 | 해당 없음. 다만 CAD 분기가 부분 가림을 자동으로 돕지는 않음 |

강한 인과 주장(“로봇 상태가 정확해서 좋아졌다”)에는 robot-state mismatch 대조와 용량 대조가 더 필요하다. 이번 CAD-only는 첫 분리 검사다.

## 실험 조건

| 항목 | 값 |
| --- | --- |
| 학습 cache | `outputs/omy_training_5080_003/motion-{train,validation}` (temporal, hypothesis_mode previous, train 1,925 / val 478). manifest sha256 train `cb18c1f5…`, val `9539d143…`. 학습 경로로 재계산해 차이 0.0 확인([FK 감사](OMY_FK_AUDIT_RESULTS.md)) |
| 학습 | 20 epochs, batch 4, warmup 0, 신규 모듈 LR 1e-4, heads LR 1e-5, AdamW, clip 1.0, seed 42/43/44 독립 초기화, visual encoder frozen |
| 모델 선택 | one-step validation 최저 best.pt (rollout을 보고 고르지 않음) |
| cad-only 정의 | is_robot 채널이 0인 CAD 256행만 같은 RobotEncoder(128/32 region)·fusion·heads에 넣는다. 로봇 행은 0으로 만들지 않고 아예 뺀다. `forward_tokens` 공통 경로라 학습과 rollout이 같다. 점 수가 256이고 geometry는 768이다 |
| 평가 | 9 validation, oracle-first-frame, 이후 GT reset 없음, frame 0 제외, refinement 2회, 평가 CAD 4,096점 seed 2026, 대칭 미선언 surface error |
| 비교군 | pretrained visual, kinematic-refine (같은 commit에서 seed마다 재실행. 결정적이라 3번이 같고 독립 반복으로 세지 않음) |
| 코드 | 학습 `8f64440`/`9784389`(학습 코드 동일, 변경 없는 tree), rollout 135개 모두 `9784389` clean. checkpoint hash 일치 확인(`provenance.json`) |

CAD 점은 물체 자기 좌표계 값(CAD/diameter)이라 가설 pose와 무관하게 물체마다 일정하다. 그래서 CAD-only 분기가 줄 수 있는 것은 물체 형상(종류)과 추가 용량이다. 위치 정보는 없다. FoundationPose의 visual token에는 이미 CAD 렌더링이 들어가므로, CAD-only는 **“분기 추가·물체 조건화 효과”의 대조군**으로 해석한다.

## 학습 (one-step validation)

학습 전: 입력 가설 18.58mm, pretrained 한 스텝 5.09mm.

| mode | seed | epoch 0 val | best val (epoch) | last val | last train | 시간 (s) | peak CUDA (MiB) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| visual | 42 | 4.31 | 3.60 (18) | 3.65 | 2.49 | 253* | 151 |
| visual | 43 | 4.34 | 3.58 (18) | 3.70 | 2.49 | 94 | 151 |
| visual | 44 | 4.31 | 3.60 (14) | 3.67 | 2.48 | 94 | 151 |
| cad-only | 42 | 4.25 | 3.60 (18) | 3.74 | 2.00 | 199* | 193 |
| cad-only | 43 | 4.25 | 3.65 (18) | 3.72 | 2.04 | 168 | 193 |
| cad-only | 44 | 4.25 | 3.69 (14) | 3.75 | 2.03 | 169 | 193 |
| geometry | 42 | 4.23 | 3.52 (19) | 3.52 | 1.74 | 169 | 193 |
| geometry | 43 | 4.19 | 3.61 (17) | 3.67 | 1.71 | 167 | 193 |
| geometry | 44 | 4.20 | 3.61 (14) | 3.68 | 1.70 | 166 | 193 |

\* FK 감사·분석 작업이 CPU를 같이 쓰던 시간이라 느려졌다(수치에는 영향 없음). visual과 geometry의 best val은 이전 motion 단계 실행과 소수점까지 같다(같은 seed에서 결정적으로 재현됨). cad-only는 256점만 쓰지만 시간과 메모리는 geometry와 비슷했다. train 오차는 visual 2.49 > cad-only 2.0 > geometry 1.7mm 순이다. 반면 val은 세 모드 모두 3.5–3.7mm로 비슷해 train–val 격차가 크다. TensorBoard 로그는 각 run의 `tensorboard/`에 있다.

## 추적 결과 (seed 평균 [최소–최대], mm)

| 방법 | macro 평균 | p95 | 마지막 | 0.1 diam 초과 (%) | 쉬운 7개 | cylinder_A_04 | cylinder_C_04 | cylinder_C_04 마지막 | 놓침 (run) | ms/frame |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| visual (pretrained) | 3.37 | 8.49 | 3.47 | 5.05 | 2.10 | 3.45 | 12.13 | 16.84 | 0/3 | 29 |
| kinematic-refine | 3.23 | 8.46 | 2.97 | 3.28 | 2.11 | 3.40 | 10.93 | 12.07 | 0/3 | 30 |
| visual-ft | 6.76 [6.71–6.81] | 25.98 | 22.79 | 8.23 | 1.00 | 5.09 [5.03–5.16] | 48.75 [48.35–49.31] | 199.4 | 3/3 | 29 |
| **cad-only** | 4.27 [2.85–6.69] | 15.09 | 9.29 | 8.26 | 1.00 | 6.59 [4.70–10.07] | 24.81 [8.63–47.93] | 72.0 [0.27–198.7] | 1/3 | 44 |
| **geometry** | **2.34 [2.01–2.66]** | 6.15 | 2.39 | 5.08 | 1.02 | **1.45 [1.27–1.63]** | 12.45 [9.41–15.50] | 15.1 [11.7–16.8] | **0/3** | 43 |

놓침 = cylinder_C_04 마지막 오차 50mm 초과. 다른 시퀀스에서는 어느 방법도 놓치지 않았다. cad-only의 ms/frame에는 사용하지 않는 로봇 FK 계산도 들어간다(평가 코드가 모든 학습 모델에 768점을 만든 뒤 모델 안에서 CAD 행만 고른다).

seed별 표(median, p95, final 포함)와 시퀀스별 값: [`summary_tables.md`](results/omy_validation_5080_004/tables/summary_tables.md), [`tracking_per_sequence.csv`](results/omy_validation_5080_004/tables/tracking_per_sequence.csv).

### seed별 paired 차이 (A − B, mm, 음수면 A가 좋음)

| 쌍 | seed | 전체 9개 | 쉬운 7개 | cylinder_A_04 | cylinder_C_04 | cylinder_C_04 마지막 | A가 나은 시퀀스 (9개 중) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geometry − cad-only | 42 | −0.93 | +0.04 | −3.26 | −5.43 | +0.00 | 4 |
| geometry − cad-only | 43 | −0.19 | +0.03 | −8.80 | +6.88 | +16.43 | 3 |
| geometry − cad-only | 44 | −4.68 | −0.03 | −3.36 | −38.53 | −187.01 | 5 |
| cad-only − visual-ft | 42 | −3.43 | −0.01 | −0.33 | −30.47 | −181.02 | 6 |
| cad-only − visual-ft | 43 | −3.96 | +0.01 | +4.91 | −40.68 | −199.98 | 4 |
| cad-only − visual-ft | 44 | −0.07 | +0.01 | −0.07 | −0.65 | −1.26 | 5 |
| geometry − kinematic-refine | 42 | −0.89 | −1.08 | −1.96 | +1.52 | +4.76 | 8 |
| geometry − kinematic-refine | 43 | −0.57 | −1.09 | −2.13 | +4.58 | +4.64 | 8 |
| geometry − kinematic-refine | 44 | −1.23 | −1.11 | −1.78 | −1.52 | −0.34 | 9 |

쉬운 시퀀스에서 geometry와 cad-only의 “나은 시퀀스 수”가 3–5개로 갈리는 것은 0.0x mm 차이다. 의미 있는 차이는 가림 두 시퀀스에서만 나온다. 전체 쌍은 [`paired_differences.csv`](results/omy_validation_5080_004/tables/paired_differences.csv)에 있다.

## 가림 전/중/후 분석

가시 비율은 GT 물체 실루엣(이미지 경계 밖을 따로 세는 padded canvas) 대비 visible mask 픽셀이다. 분석에만 쓰고 모델 입력이나 gate로는 쓰지 않았다. 9개 validation 모두 물체가 이미지 밖으로 나가지 않았고(in-image 비율 1.0), mask가 실루엣 밖에 걸친 픽셀은 최대 5개였다. 이전 audit과 평균 가시 비율 차이는 0.003 이하다.

**정의(사전 고정):** bin ≥50 / 20–50 / 5–20 / <5%. 심한 가림 = <5%가 3프레임 이상 연속. 재등장 = 그 뒤 ≥50%가 3프레임 연속되는 첫 시작. 회복 = 재등장 이후 오차 ≤ 0.1 diameter가 5프레임 연속되는 첫 시작. 심한 가림 사건은 cylinder_C_04 하나뿐이다(frame 129–135, 139–183 → 하나로 합침, 재등장 frame 199).

### 가시 비율 bin별 평균 오차 (mm, 학습 모델은 3 seed run 평균 [run 범위])

| bin | 프레임 / 시퀀스 | visual | kinematic-refine | visual-ft | cad-only | geometry |
| --- | --- | --- | --- | --- | --- | --- |
| ≥50% | 1,379 / 9 | 2.33 | 2.15 | 7.58 [7.57–7.60] | 3.71 [1.59–7.47] | 1.58 [1.33–1.89] |
| 20–50% | 761 / 8 | 3.27 | 3.21 | 2.49 [2.46–2.52] | 2.20 [1.72–2.49] | 1.69 [1.37–1.92] |
| 5–20% | 181 / 3 | 4.43 | 4.43 | 9.71 [9.24–9.97] | 9.22 [8.27–9.85] | 4.22 [3.58–4.56] |
| <5% | 52 / 1 | 26.92 | 26.73 | 23.64 [22.58–24.46] | 23.79 [20.37–27.86] | 22.52 [21.79–23.89] |

≥50% bin에는 cylinder_C_04 재등장 후(가시 100%) 프레임이 들어 있어, 물체를 놓친 run(visual-ft, cad-only s44)의 평균이 높다. 5–20% bin(심한 부분 가림)에서 geometry만 pretrained 수준(4.2mm)을 유지하고, visual-ft·cad-only는 약 9–10mm로 두 배다.

### cylinder_C_04 구간별 평균 오차 (mm, seed 42 / 43 / 44)

| 구간 | 프레임 | visual | kinematic-refine | visual-ft | cad-only | geometry |
| --- | --- | --- | --- | --- | --- | --- |
| 가림 전 (2초) | 60 | 3.8 | 4.3 | 7.3 / 9.2 / 7.5 | 8.1 / 7.1 / 8.0 | 4.8 / 4.9 / 3.8 |
| 가림 중 (<5% ~ 재등장 전) | 70 | 23.9 | 22.8 | 32.8 / 33.5 / 33.5 | 30.0 / 22.3 / 32.6 | 25.7 / 29.6 / 19.6 |
| 재등장 후 | 53 | 16.8 | 12.1 | 174.4 / 175.7 / 174.2 | 33.0 / 0.3 / 171.9 | 16.8 / 26.2 / 12.2 |

### cylinder_C_04 회복 (사전 지표 + 보충 분해)

| run | 가림 중 최대 | 회복 상태 | 회복 시간 | 재등장 +1s | 마지막 | 마지막 위치 오차 | 마지막 회전 오차 (축, mesh) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| visual | 44.8 | 미회복 | — | 16.8 | 16.8 | 0.9mm | 175.5° (y) |
| kinematic-refine | 44.9 | 회복 | 0.40s | 12.0 | 12.1 | 0.9mm | 91.3° (y) |
| visual-ft s42/43/44 | 89 / 85 / 85 | 미회복 ×3 | — | 205 / 205 / 204 | 198 / 200 / 200 | 198–200mm | — (놓침) |
| cad-only s42 | 84.1 | 미회복 | — | 16.8 | 16.8 | 0.5mm | 174.4° (y) |
| cad-only s43 | 40.2 | 회복 | 0.0s | 0.2 | **0.3** | 0.1mm | **0.8°** |
| cad-only s44 | 81.4 | 미회복 | — | 203 | 198.7 | 199mm | — (놓침) |
| geometry s42 | 52.6 | 미회복 | — | 16.8 | 16.8 | 0.3mm | 173.5° (y) |
| geometry s43 | 82.8 | 미회복 | — | 16.7 | 16.7 | 1.0mm | 164.7° (y) |
| geometry s44 | 32.6 | 회복 | 0.77s | 12.0 | 11.7 | 1.1mm | 88.0° (y) |

회복 기준(0.1 diameter = 12.1mm)이 긴 축 90° 회전 오차(약 12mm)와 거의 같아서, “회복/미회복”은 회전 오차가 약 90°인지 약 170°인지에 따라 갈린다. 실제 결과는 둘로 나뉜다. (a) 물체를 놓쳐 약 200mm. (b) 위치는 1mm 안쪽으로 되찾았지만 긴 축 회전을 잃음. cad-only s43만 회전까지 되찾았다. 이전 runs(pilot·motion 단계, 다른 commit)에서도 놓치지 않은 run은 모두 위치 오차 0.3–1.1mm, 회전 오차 85–175°(y축)였다([reference recovery_events.csv](results/omy_validation_5080_004/occlusion/reference_earlier_runs_recovery_events.csv)).

### 그림

- [cylinder_C_04 전체 타임라인 (seed 42)](results/omy_validation_5080_004/figures/cylinder_C_04_full.png): 위 가시 비율, 가운데 방법별 오차(log), 아래 link6 속력(측정 관절 FK)과 물체 속력(GT, 분석 전용). task_phase 표시는 시뮬레이터 label이며 분석 전용이다.
- [cylinder_C_04 전환 구간 확대](results/omy_validation_5080_004/figures/cylinder_C_04_transition0.png): release 순간(약 4.2s) 물체가 최대 36cm/s로 움직이고 곧바로 가려진다.
- [cylinder_C_04 모든 seed](results/omy_validation_5080_004/figures/cylinder_C_04_all_seeds.png), [cylinder_A_04 모든 seed](results/omy_validation_5080_004/figures/cylinder_A_04_all_seeds.png), [cylinder_A_04 타임라인](results/omy_validation_5080_004/figures/cylinder_A_04_full.png)
- [cylinder_C_04 위치/회전 분해 (보충)](results/omy_validation_5080_004/figures/cylinder_C_04_translation_rotation.png)
- overlay keyframe (seed 42, cylinder_C_04): [geometry 재등장 f199](results/omy_validation_5080_004/figures/overlay_cylinder_C_04_s42_geometry_f199.png) — 예측 상자(cyan)는 GT 상자(magenta)와 겹치지만 X/Y 축 방향이 다르다(긴 축 회전). [visual-ft 마지막 f250](results/omy_validation_5080_004/figures/overlay_cylinder_C_04_s42_visual-ft_f250.png), [cad-only 마지막 f250](results/omy_validation_5080_004/figures/overlay_cylinder_C_04_s42_cad-only_f250.png). 색 규약: 예측 cyan 실선, GT magenta 점선, 측정 FK 로봇 주황(X-ray, depth test 없음).
- overlay 영상(로컬): `outputs/omy_validation_5080_004/analysis/videos/` — seed 42의 cylinder_A_04·cylinder_C_04 × {kinematic-refine, visual-ft, cad-only, geometry}. 추가로 cylinder_C_04의 cad-only s43(유일한 완전 회복)과 s44(cad-only 중 유일한 놓침)를 만들었다. seed 42는 사전에 정한 공통 시각화 seed다.

cylinder_A_04 그림에서 visual-ft와 cad-only는 가림 구간(2.3–6s)에 오차가 약 17mm로 뛴다. 이것도 긴 축 회전이 뒤집힌 패턴과 같은 크기다. cad-only s43은 가림이 끝나도 17mm에 머물러 평균 10.07mm가 됐다. geometry는 3개 seed 모두 가림 중 2–4mm를 유지했다.

## 이전 결과와의 관계

- pilot(perturbed cache)과 motion 단계(temporal motion 모드) 결과는 다른 commit에서 만든 reference로 둔다. 이번 matched 표와 섞지 않았다. 같은 그림·지표로 다시 분석한 결과는 `outputs/omy_validation_5080_004/analysis/reference_earlier_runs/`에 있다.
- 이번에 다시 학습한 temporal visual·geometry는 이전 motion 단계 결과와 best val·추적 macro가 같다(geometry 2.34/2.66/2.01, visual-ft 6.71/6.81/6.75).

## 한계

- oracle-first-frame 초기화. validation 9개를 best.pt 선택과 평가에 함께 썼고 독립 test가 없다.
- 가림 결론은 사실상 시퀀스 2개(cylinder_A_04 부분 가림, cylinder_C_04 완전 가림)에 근거한다. 완전 가림 사건은 하나뿐이다. seed 3개는 독립 장면 3개가 아니다.
- 두 핵심 시퀀스가 모두 거의 원통인 마커이고 대칭이 선언되지 않았다. surface error의 상당 부분이 긴 축 회전 모호성에서 나온다. 회전 분해는 사후에 추가한 보충 분석이다.
- cad-only는 256점, geometry는 768점이라 계산량과 sampling이 다르다. 점 수를 맞춘 대조(cad-only-768)는 하지 않았다.
- 로봇 상태가 “정확해서” 도움이 되는지는 아직 검사하지 않았다(robot-state mismatch 대조 미실시).
- 시뮬레이션, 고정 카메라, 시뮬레이터 내부 FK 정합(PASS)만 확인했다.

## 미완료 / 하지 않은 것

- cad-only-768 점 수 대조: 선택 항목, 이번 9회와 섞지 않기 위해 실행하지 않음.
- robot-state mismatch(다른 시점·다른 시퀀스의 로봇 상태) 대조, 용량 대조: 범위 밖.
- 대칭 선언 또는 회전 모호성을 반영한 지표: 평가 지표를 바꾸지 않는다는 규칙에 따라 보충 분석으로만 보고했다.

## 다음 단계 제안 (결과 근거, 실행하지 않음)

1. **원통형 물체 지표 정리**: 마커의 긴 축 대칭을 데이터 쪽에서 선언할지(텍스처가 있으면 완전 대칭이 아님), 아니면 위치·회전 분리 지표를 정식 지표로 추가할지 정한다. 지금은 “회복”이 회전 90° vs 170°로 갈린다.
2. **robot-state mismatch 대조**: geometry를 그대로 두고 추론 때 로봇 상태를 다른 시점의 것으로 바꿔, cylinder_A_04 개선이 실제 로봇 위치에서 오는지 확인한다.
3. **가림 데이터 추가**: 완전 가림 + 재등장 사건이 train 6개, validation 1개뿐이다. 데이터 팀 요청의 근거로 쓴다.
4. cad-only s43처럼 회전까지 되찾는 경우가 우연인지 보려면 seed를 늘리거나 사건 수를 늘려야 한다.

## 재현

```bash
conda activate rafp
R=outputs/omy_validation_5080_004; W=outputs/omy_training_5080_003
for seed in 42 43 44; do for mode in visual cad-only geometry; do
  python scripts/train_robot_refiner.py --train $W/motion-train --val $W/motion-validation --mode $mode --seed $seed \
    --epochs 20 --batch-size 4 --warmup-epochs 0 --lr 1e-4 --head-lr 1e-5 --output $R/training/temporal-$mode-s$seed
done; done
for seed in 42 43 44; do
  python scripts/run_omy_comparison.py --dataset "$OMY_DATASET" --initial-poses outputs/omy_comparison_5080_001/initial-oracle \
    --initialization oracle-first-frame --iterations 2 --methods visual kinematic-refine \
    --checkpoint visual-ft=$R/training/temporal-visual-s$seed/best.pt \
    --checkpoint cad-only=$R/training/temporal-cad-only-s$seed/best.pt \
    --checkpoint geometry=$R/training/temporal-geometry-s$seed/best.pt \
    --output $R/evaluation/seed-$seed --execute
done
python scripts/summarize_cad_ablation.py --training $R/training --evaluation $R/evaluation \
  --reference $W/pretrained_reference_motion.json --output $R/analysis/tables
python scripts/measure_omy_visibility.py --dataset "$OMY_DATASET" --output $R/analysis/visibility_per_frame.csv
python scripts/analyze_occlusion_rollouts.py --visibility $R/analysis/visibility_per_frame.csv --dataset "$OMY_DATASET" \
  --output $R/analysis/matched --run visual=$R/evaluation/seed-42/visual --run kinematic-refine=$R/evaluation/seed-42/kinematic-refine \
  --run visual-ft/s42=$R/evaluation/seed-42/visual-ft ...   # 9개 학습 run 모두
```

전체 산출물(로컬): `outputs/omy_validation_5080_004/` — `plan.json`, `environment.txt`, `provenance.json`, `training/`(checkpoint, metrics.jsonl, TensorBoard), `evaluation/seed-*/`, `analysis/`.
