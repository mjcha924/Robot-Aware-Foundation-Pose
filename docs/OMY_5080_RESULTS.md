# OMY 실험 결과 — RTX 5080 (2026-11-26)

baseline → tiny → pilot(3 seed) → motion 단계(3 seed)의 결과 정리. 코드 기준 커밋은 `5dfe0a9`(이 문서 커밋 직전)이다.

**모든 추적 수치는 첫 프레임을 GT로 시작한 oracle-first-frame 조건이며, 실사용 초기화 성능이 아니다.**

## 핵심 요약

**temporal cache로 학습한 geometry 모델만 3개 seed 모두에서 kinematic-refine(3.23mm)을 이겼고(2.01–2.66mm), 가림 시퀀스에서 물체를 한 번도 놓치지 않았다(0/3).**

validation 9개 시퀀스의 연속 추적(rollout) 평균 표면 오차(mm). 학습 모델은 3 seed 평균 [최소–최대].

| 방법 | 전체 macro | 쉬운 7개 | cylinder_A_04 (부분 가림) | cylinder_C_04 (완전 가림 후 해제) | cylinder_C 놓침* |
| --- | --- | --- | --- | --- | --- |
| visual (pretrained, 학습 없음) | 3.37 | 2.10 | 3.45 | 12.13 | 0/1 |
| **kinematic-refine (기준선)** | **3.23** | 2.11 | 3.40 | **10.93** | 0/1 |
| pilot visual-ft | 7.13 [6.66–7.38] | 1.02 [1.00–1.04] | 8.59 [4.82–10.55] | 48.45 [47.86–48.79] | 3/3 |
| pilot geometry | 4.67 [1.90–6.09] | 1.04 [0.99–1.13] | 1.39 [1.20–1.48] | 33.34 [8.71–45.83] | 2/3 |
| temporal visual | 6.76 [6.71–6.81] | 1.00 [0.97–1.02] | 5.09 [5.03–5.16] | 48.75 [48.35–49.31] | 3/3 |
| **temporal geometry** | **2.34 [2.01–2.66]** | 1.02 [1.00–1.02] | **1.45 [1.27–1.63]** | 12.45 [9.41–15.50] | **0/3** |
| temporal motion | 3.21 [2.05–5.51] | 1.05 [1.00–1.10] | 1.64 [1.39–2.04] | 19.88 [9.67–39.90] | 1/3 |

\* 놓침 = 마지막 프레임 오차 50mm 초과(물체 대신 그리퍼를 따라감). 학습 없는 방법은 1회 실행.

확인된 결론:

1. **로봇 정보가 가림 상황에서 끌려가는 것을 막는다.** 로봇 정보 없는 미세조정(visual-ft, temporal visual)은 cylinder_C_04를 6/6 놓쳤고, geometry는 cylinder_A_04에서 6/6 모두 1.2–1.6mm를 유지했다.
2. **추가 학습만으로는 가림에 더 약해진다.** 쉬운 시퀀스는 2.1 → 1.0mm로 좋아지지만 visual-only 모델은 그리퍼에 붙어간다.
3. **temporal cache가 geometry를 안정화했다.** 같은 모델에서 cylinder_C 놓침이 2/3 → 0/3.
4. **속도 정보(motion)는 이득이 없었다.** 평균이 geometry보다 나쁘고 seed 1개에서 놓쳤다.
5. **완전 가림 후 복구는 미해결이다.** 물체를 놓치지 않은 방법도 모두 cylinder_C_04를 약 12–17mm 오프셋으로 끝내며 kinematic-refine(10.93)보다 낫지 않다.
6. **one-step validation 오차로는 추적 성능을 고를 수 없다.** 모든 모델이 약 3.5–3.6mm인데 추적 결과는 최대 20배 차이.

## 실험 설정

- 데이터: OMY pilot 시뮬레이션(checksum 37,654개 검증). 물체 3종(asymmetric, box, cylinder) × 시나리오 A/B/C, 00–03 train, 04 validation. cache: train 1,926 / val 478(stride 5), tiny 48.
- 모델(RobotConditionedRefiner): FoundationPose pretrained refiner(2023-10-28-18-33-37) visual encoder 고정, RobotEncoder(로봇 FK 표면점 512 + CAD 256, 점당 11채널) → residual cross-attention(alpha 초기 0.01).
  - visual = 로봇 분기 없음 · geometry = 속도 채널(6:9, 10) 0 · motion = 전체 채널.
- cache: **perturbed** = 현재 GT + 노이즈(trans σ 0.01m, rot σ 10°), **temporal** = 이전 프레임 GT를 현재 카메라 좌표계로 옮긴 뒤 + 노이즈. 입력 오차는 둘 다 약 18.5–19mm.
- 학습: 20 epoch, seed 42/43/44, best.pt(one-step val 최저)로 평가.
- 평가(rollout protocol 2): 첫 프레임 GT 초기화 후 제외, GT 재설정 없음. CAD 평가점 4,096개(seed 2026) 평균 표면 오차, 9개 시퀀스 macro. 실패 = diameter 10% 초과.
- 비교: hold(이전 pose 유지), kinematic(link6 강체 가정), visual(pretrained), kinematic-refine(kinematic + pretrained 보정).

## 환경과 코드 수정

conda `rafp`: Python 3.10, torch 2.8.0+cu128, nvcc 12.8, nvdiffrast 0.3.3, pytorch3d 0.7.8(sm_120 소스 빌드), trimesh 4.12.2(<5 고정), tensorboard 2.21.

| 커밋 | 내용 |
| --- | --- |
| e520457 | decode_pose 회전 delta를 transpose로 적용(upstream과 일치). 수정 전 cache/checkpoint 재사용 금지 |
| 825a71a | upstream crop helper에 float64 diameter 전달 |
| 2160016 | TensorBoard 로깅(`--no-tensorboard`로 끔) |
| 5dfe0a9 | kinematic 전파를 float64로 계산(frame 274 validate_pose 실패 해결) |

trimesh 5는 `np.random.seed`를 무시해 CAD 샘플이 재현되지 않으므로 <5로 고정했다.

## 베이스라인 (학습 없음)

| 방법 | 전체 평균 (mm) | 마지막 프레임 (mm) | 실패 프레임 (%) | A / B / C 평균 (mm) | 프레임당 (ms) |
| --- | --- | --- | --- | --- | --- |
| hold | 60.88 | 106.64 | 44.1 | 0.00 / 54.66 / 127.99 | 0.08 |
| kinematic | 71.47 | 102.51 | 70.4 | 60.21 / 89.55 / 64.66 | 0.55 |
| visual | 3.37 | 3.47 | 5.1 | 2.44 / 2.62 / 5.05 | 29.7 |
| kinematic-refine | 3.23 | 2.97 | 3.3 | 2.42 / 2.63 / 4.64 | 30.3 |

- pretrained one-step 기준(`scripts/measure_pretrained_reference.py`): perturbed val 입력 18.5 → 5.06mm, temporal val 5.09mm.
- tiny: train 5.23 → 2.66mm, val 최저 4.97mm(epoch 3) 후 과적합(5.95mm), 30초.

## Pilot 3-seed (perturbed cache)

| 모델 | seed | one-step val 최저 (mm, epoch) | 추적 macro (mm) | 실패 프레임 (%) | cylinder_A_04 (mm) | cylinder_C_04 마지막 (mm) |
| --- | --- | --- | --- | --- | --- | --- |
| visual-ft | 42 | 3.54 (19) | 6.66 | 6.3 | 4.82 | 197.6 |
| visual-ft | 43 | 3.57 (15) | 7.35 | 12.4 | 10.4 | 197.5 |
| visual-ft | 44 | 3.61 (14) | 7.38 | 12.5 | 10.6 | 200.7 |
| geometry | 42 | 3.47 (16) | 1.90 | 3.0 | 1.48 | 11.6 |
| geometry | 43 | 3.53 (14) | 6.01 | 5.4 | 1.20 | 192.6 |
| geometry | 44 | 3.48 (18) | 6.09 | 5.4 | 1.48 | 198.8 |

seed 42 geometry의 cylinder_C_04 성공은 운이었다. train 끝 오차(geometry 약 1.70, visual-ft 약 2.45mm) vs val 약 3.5mm로 격차가 크다.

## Motion 단계 3-seed (temporal cache)

| 모델 | seed | one-step val 최저 (mm, epoch) | 추적 macro (mm) | 실패 프레임 (%) | cylinder_A_04 (mm) | cylinder_C_04 평균 / 최대 / 마지막 (mm) |
| --- | --- | --- | --- | --- | --- | --- |
| visual | 42 | 3.60 (18) | 6.71 | 8.0 | 5.03 | 48.35 / 207.0 / 197.8 |
| visual | 43 | 3.58 (18) | 6.81 | 8.3 | 5.16 | 49.31 / 209.5 / 200.3 |
| visual | 44 | 3.60 (14) | 6.75 | 8.4 | 5.06 | 48.58 / 208.2 / 200.0 |
| **geometry** | 42 | 3.52 (19) | **2.34** | 5.6 | 1.45 | 12.45 / 52.6 / 16.8 |
| **geometry** | 43 | 3.61 (17) | **2.66** | 5.6 | 1.27 | 15.50 / 86.7 / 16.7 |
| **geometry** | 44 | 3.61 (14) | **2.01** | 4.1 | 1.63 | 9.41 / 32.6 / 11.7 |
| motion | 42 | 3.55 (12) | 5.51 | 5.5 | 2.04 | 39.90 / 160.5 / 158.1 |
| motion | 43 | 3.54 (17) | 2.05 | 4.6 | 1.39 | 9.67 / 33.1 / 12.3 |
| motion | 44 | 3.56 (14) | 2.06 | 3.6 | 1.50 | 10.08 / 37.3 / 11.4 |

비교 기준 kinematic-refine: macro 3.23, cylinder_A_04 3.40, cylinder_C_04 10.93 / 44.9 / 12.1mm.

## 가림 분석

가시 비율 = GT pose로 렌더링한 물체 실루엣 대비 mask 픽셀 비율(`outputs/omy_comparison_5080_001/visibility_audit.json`).

**완전 가림(가시 5% 미만 프레임이 있는 시퀀스)은 전체 7개뿐이고 validation에는 cylinder_C_04 하나다.**

| 시퀀스 | split | 평균 가시 비율 | 가시 20% 미만 (%) | 가시 5% 미만 (%) | 가시 50% 미만 최장 연속 (frame) |
| --- | --- | --- | --- | --- | --- |
| cylinder_C_04 | validation | 0.41 | 38.9 | 20.6 | 164 |
| cylinder_C_00 | train | 0.40 | 37.7 | 28.5 | 154 |
| cylinder_C_01 | train | 0.39 | 40.0 | 33.8 | 160 |
| cylinder_C_02 | train | 0.41 | 38.6 | 19.7 | 163 |
| cylinder_C_03 | train | 0.38 | 38.0 | 28.2 | 182 |
| box_C_00 | train | 0.53 | 23.7 | 9.7 | 119 |
| box_C_01 | train | 0.50 | 28.1 | 5.5 | 128 |

- cylinder_C_04: frame 129–183 동안 가시 5% 미만, 약 frame 210부터 100% 보임. 그 사이 kinematic-refine과 temporal geometry는 33–87mm까지 끌려갔다 돌아오고, temporal visual은 약 200mm로 그리퍼를 따라간다. 다시 보여도 원위치로 돌아오는 방법은 없다.
- validation 중 가시 20% 미만 프레임이 있는 것은 cylinder_C_04, box_A_04(28.8%), cylinder_A_04(27.5%)뿐이다.

## 시간·GPU 자원 (실측)

| 단계 | 시간 | peak GPU 메모리 |
| --- | --- | --- |
| prepare (train + val + tiny) | 3분 39초 | 약 1.7GB |
| tiny 학습 (20 epoch) | 29초 | 137MiB |
| visual 학습 (20 epoch) | 94–100초 (한 번 188초) | 151MiB |
| geometry / motion 학습 (20 epoch) | 166–173초 | 193MiB |
| motion 단계 추적 평가 (seed당) | 약 489초 | — |

프레임당 추적: pretrained 약 29–30ms, 학습 geometry/motion 약 43ms.

## 한계

- oracle-first-frame 초기화. 실사용 초기화 결과 아님.
- 가림 결론은 사실상 validation 2개(cylinder_A_04, cylinder_C_04)에 근거.
- 독립 test 없음: validation을 checkpoint 선택과 평가에 모두 사용.
- best.pt는 one-step val 기준이며 추적 성능을 예측하지 못한다.
- motion은 teacher-forced(추적 중 자기 오차 누적은 학습하지 않음).
- seed 3개, 시뮬레이션·고정 카메라.

## 다음 단계 후보

| 후보 | 답하는 질문 | 지금 가능 |
| --- | --- | --- |
| A. CAD-only ablation | 도움이 로봇 정보에서 오는가, 물체 형상에서 오는가 | 예 (코드 소규모, 약 1시간) |
| B. 추적 기준 checkpoint 선택 | best.pt 대신 추적으로 고르면 분산이 줄어드는가 | 예 (약 1시간) |
| C. On-policy cache | 자기 오차로 학습하면 가림 후 오프셋이 줄어드는가 | 예 (수 시간) |
| D. 가림 데이터 재학습 | 가림 데이터가 많으면 일반화되는가 | 데이터 대기 |
| E. 외부 초기화 | GT 없이 시작한 실사용 성능 | 예 (도구 연결 필요) |
| F. 약한 base model에 fusion | 다른 모델에서도 효과가 있는가 | 검토 필요 |

추천 순서: A → C → (데이터 도착 시) D.

## 결과 파일 (로컬, 커밋 안 함)

| 경로 | 내용 |
| --- | --- |
| `outputs/omy_comparison_5080_001/all_results_summary.txt` | 3-seed 요약표 |
| `outputs/omy_comparison_5080_001/pretrained-baselines-v2/` | 베이스라인 |
| `outputs/omy_comparison_5080_001/pilot*`, `temporal*` | 추적 평가 (`comparison.md/json`, 시퀀스별 `frame_metrics.jsonl`) |
| `outputs/omy_comparison_5080_001/visibility_audit.json` | 가시 비율 감사 |
| `outputs/omy_comparison_5080_001/videos/` | overlay 영상 |
| `outputs/omy_training_5080_003/run-*` | checkpoint, metrics.jsonl, TensorBoard |
| `outputs/omy_training_5080_003/pretrained_reference*.json` | pretrained one-step 기준값 |

후속 검증 실행 지시서: [FK 감사 · CAD-only 대조 · 결과 판정 · 가림 분석](OMY_NEXT_VALIDATION_HANDOFF.md).
