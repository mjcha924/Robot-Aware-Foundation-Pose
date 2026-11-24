# 리뷰 수정과 기구학 baseline: 실행 및 해석

이 문서는 `feat/omy-training-ready`의 새 비교 프로토콜이다. 먼저 학습 없이 hold → kinematic → visual → kinematic-refine을 비교하고, 그다음 동일 데이터로 학습한 모델을 비교한다. 원본 upstream 전체 시스템 재현이 아니라 **같은 RenderBridge에서 원본 pretrained refiner와 수정 모델을 비교**한다. 실제 OMY/5080 결과는 아직 없다.

## 1. 이번 수정이 해결하는 문제

가중치 경로: 서로 다른 컴퓨터의 `ckpt_dir` 절대 경로는 동일성 비교에서 제외한다. 대신 가중치 파일의 SHA-256과 나머지 config를 엄격히 비교한다. 다른 가중치를 같은 이름으로 바꿔도 통과하지 않는다. train/validation cache 비교, resume, CUDA 검사, rollout 모두 같은 규칙을 사용한다.

물체 diameter: 이전에는 mesh vertex를 무작위로 뽑아 계산해 crop·translation decoding의 스케일이 달라질 수 있었다. 이제 convex hull의 vertex 간 최대 거리를 정확히 계산한다. 퇴화한 평면/선 mesh는 전체 vertex를 사용하며 메모리는 작은 block으로 제한한다. 학습 cache와 rollout은 `exact-vertex-diameter-v1`을 공유한다. cache format 3에는 mesh geometry hash와 실제 diameter도 기록한다. 매우 복잡한 hull은 준비 시간이 길 수 있지만 프레임마다 계산하지 않는다.

반복 I/O/FK: OMY adapter는 manifest, 관측 JSONL, preroll, joint inventory를 한 번만 읽는다. 최근 FK 3개, 현재 frame의 robot surface, RGB-D 1개를 보관한다. 같은 프레임의 refinement에서는 hypothesis 좌표 변환만 다시 한다. 이전 surface는 이전 시점의 robot base pose도 반영한다. 공개 dataset reader 원본은 유지하며 학습 adapter가 이 경로를 직접 구현한다.

평가: 학습용 256점과 다른 seed로 면적 비례 CAD 4,096점을 뽑는다. 전체 예측을 끝낸 뒤 GT로 채점하고, 초기화 프레임을 평균에서 뺀다. 실제 rollout, 마지막 프레임 drift, 임계 초과 비율을 기록한다. `best.pt`는 여전히 **one-step validation loss 기준**이며 tracking 성능이 가장 좋은 모델이라는 뜻은 아니다.

**이전 cache와 checkpoint는 새 geometry 규약에서 거부한다. 기존 파일을 수정하거나 지우지 말고 새 OMY_WORK에서 cache 생성부터 다시 시작한다.** checkpoint의 version 문자열만 고쳐 통과시키면 안 된다.

## 2. 기구학 prior가 하는 일

`T_AB`는 B 좌표를 A 좌표로 변환한다. W는 world, C는 camera, E는 link6의 rigid frame, M은 raw object mesh다. 입력은 이전 추정 pose와 현재/이전 측정 관절값으로 계산한 FK다.

```text
T_WM(previous) = T_WC(previous) · estimated_T_CM(previous)
Delta_T_world = T_WE(current) · inverse(T_WE(previous))
prior_T_CM(current) = inverse(T_WC(current)) · Delta_T_world · T_WM(previous)
```

그리퍼와 물체가 고정된 관계를 유지하면 이 식으로 물체의 위치와 회전을 함께 예측할 수 있다. 회전 시 물체 중심이 손목을 중심으로 움직이는 lever arm도 포함한다. 단순히 gripper 이동량을 xyz에 더하는 구현과 다르다. 카메라가 움직이는 경우도 보상한다.

현재 프로젝트의 tool carrier는 `link6`다. 고정 tool offset을 양쪽 시점에 동일하게 적용하면 `T_WE(t) · inverse(T_WE(t-1))`에서 상쇄되므로 baseline에는 별도의 tool offset을 추정할 필요가 없다. 손가락처럼 gripper 개폐로 별도 운동하는 link를 선택하면 rigid-grasp 가정과 맞지 않는다. 다른 robot에서는 `--effector-link`를 명시한다. 잘못된 link 이름은 실행 초기에 거부한다.

이 prior는 **항상 rigid grasp를 가정한다**. A 비접촉 가림, B의 grasp 전 구간, C의 release 후 구간에서도 로봇을 따라가므로 틀릴 수 있다. GT contact/phase로 적절한 구간만 골라 prior를 적용하지 않는다. 이는 baseline의 알려진 가정이며, 바로 그 실패가 학습 모델이 해결해야 할 비교 대상이다. 마찰·slip·외력은 모델링하지 않는다.

## 3. 비교할 방법

`hold`: 물체가 world에 고정돼 있다고 가정하고 camera motion만 보상한다. RGB-D나 신경망을 사용하지 않는 CPU control이다. A/C에서 물체가 정지해 있는 비중이 높아 평균이 좋게 보이는지 확인한다.

`kinematic`: 매 프레임 위 식으로만 propagate한다. CPU에서 실행하며 학습·FoundationPose weights·CUDA가 필요 없다. 단, torch/numpy/scipy/trimesh/Pillow 등 reader 의존성은 필요하다.

`visual`: 직전 추정 pose에 camera motion만 보상한 뒤 pretrained FoundationPose refiner를 적용한다. robot input은 사용하지 않는다.

`kinematic-refine`: 기구학 prior를 한 프레임당 한 번 적용한 뒤 **동일 pretrained refiner**로 보정한다. refinement를 2번 해도 prior를 2번 적용하지 않는다. 새 학습 파라미터가 없다. 신경망 fusion이 넘어야 할 가장 중요한 단순 비교 대상이다.

`learned`: 학습된 checkpoint의 visual / geometry / motion 모드로 추적한다. 기구학 prior는 자동으로 추가하지 않는다. 모델 자체가 robot 정보를 어떻게 쓰는지 평가하기 위해서다. 두 기법을 결합하는 실험은 이번 구현의 범위 밖이다.

모든 방법은 같은 frame-0 `T_camera_raw_mesh`를 그대로 출력하고 **frame 1부터 추적**한다. frame 0에 어떤 방법만 추가 refinement를 해 유리한 출발점을 만들지 않는다. 중간 GT reset, oracle mask, 실패 후 자동 재초기화는 없다. 기존 evaluator의 frame-0 refinement 결과와 새 protocol 2 결과를 직접 섞지 않는다.

## 4. 준비: 업데이트와 GPU gate

아래 명령은 기존 clone의 작업이 저장된 상태에서 실행한다. 새 clone과 환경 구성은 RUN_ON_5080.md의 1~5단계를 따른다. 최신 코드의 smoke를 통과한 뒤 GPU baseline을 실행한다. raw dataset이나 weights가 GitHub에서 자동으로 내려오지는 않는다.

```bash
git switch feat/omy-training-ready
git pull --ff-only origin feat/omy-training-ready
git submodule update --init --recursive
python -m pytest -q
export OMY_WORK="$PWD/outputs/omy_training_002"
export OMY_EVAL="$PWD/outputs/omy_comparison_002"
# OMY_DATASET과 OMY_CHECKSUMS는 RUN_ON_5080.md에서 지정한 실제 경로 사용.
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage smoke --checksums "$OMY_CHECKSUMS" --execute
```

이미 최신 geometry 규약으로 smoke를 통과했다면 같은 출력 경로에서 반복할 필요가 없다. 모든 출력 디렉터리는 기존 결과를 덮어쓰지 않는다.

## 5. 초기 pose: 먼저 tracking만 진단

첫 비교는 initialization 실패와 tracking 실패를 분리하기 위해 **동일한 첫 프레임 GT 초기화**로 진단할 수 있다. 아래 명령은 의도적으로 정답을 읽는 별도 준비 도구다. 이후 tracker가 GT를 받아 매번 보정하는 것은 아니다. 결과에 `oracle-first-frame`이 기록되며 실사용 초기화 성능으로 보고하면 안 된다.

```bash
python scripts/prepare_omy_initial_poses.py --dataset "$OMY_DATASET" \
  --output "$OMY_EVAL/initial-oracle" --oracle-first-frame
export OMY_INITIAL="$OMY_EVAL/initial-oracle"
export OMY_INIT_KIND=oracle-first-frame
```

실제 초기화 비교에서는 외부 FoundationPose registration 결과를 `initial-external/<sequence>.npy`로 저장한다. 9개 validation sequence 각각에 4×4 행렬 하나가 필요하며 dtype은 float32/64, 단위는 m다. 좌표는 object-root나 centered-mesh가 아닌 raw mesh 기준이다. 자동 registration 도구는 이번 변경에 포함되지 않는다. 준비 후 위 두 환경변수를 아래처럼 교체한다.

```bash
export OMY_INITIAL="$OMY_EVAL/initial-external"
export OMY_INIT_KIND=external
```

Oracle용 파일을 external로 재명명해서 사용하지 않는다. 준비 도구가 남긴 `initialization.json`과 실행 옵션이 다르면 suite는 거부한다. external 초기화의 성공 여부와 초기 오차는 tracking과 따로 보고한다.

## 6. 학습 없는 baseline부터 실행

먼저 CPU baseline 둘을 확인한다. `--execute`를 빼면 명령만 보여준다. 기본 분할은 고정된 validation 9개이며 train으로 바꾸지 않는다.

```bash
python scripts/run_omy_comparison.py --dataset "$OMY_DATASET" \
  --initial-poses "$OMY_INITIAL" --initialization "$OMY_INIT_KIND" \
  --methods hold kinematic --output "$OMY_EVAL/cpu-baselines" --execute
```

다음은 pretrained visual을 포함한 4개 비교다. CPU baseline도 같은 suite에 다시 실행해 하나의 결과표로 묶는다. GPU는 한 번에 한 작업만 사용한다.

```bash
python scripts/run_omy_comparison.py --dataset "$OMY_DATASET" \
  --initial-poses "$OMY_INITIAL" --initialization "$OMY_INIT_KIND" \
  --output "$OMY_EVAL/pretrained-baselines" --execute
cat "$OMY_EVAL/pretrained-baselines/comparison.md"
```

한 시퀀스만 먼저 확인하려면 다음 명령을 쓴다. box_B_04에 대해 visual과 kinematic-refine을 같은 initial/iterations로 비교한다.

```bash
python scripts/evaluate_robot_tracker.py "$OMY_DATASET/box_B_04" \
  --initial-pose "$OMY_INITIAL/box_B_04.npy" --initialization "$OMY_INIT_KIND" \
  --method visual --iterations 2 --output "$OMY_EVAL/one-visual"
python scripts/evaluate_robot_tracker.py "$OMY_DATASET/box_B_04" \
  --initial-pose "$OMY_INITIAL/box_B_04.npy" --initialization "$OMY_INIT_KIND" \
  --method kinematic-refine --effector-link link6 --iterations 2 \
  --output "$OMY_EVAL/one-kinematic-refine"
```

## 7. 학습 및 학습 모델 비교

아직 최신 cache가 없다면 다음을 순서대로 실행한다. tiny loss가 줄지 않으면 pilot로 확대하지 않는다. prepare는 GPU rendering과 feature 추출, tiny/pilot은 cache에서 학습하는 과정이다.

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage prepare --checksums "$OMY_CHECKSUMS" --execute
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage tiny --execute
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage pilot --execute
```

학습 전 baseline 4개와 pilot visual/geometry 두 개를 같은 조건으로 비교한다.

```bash
python scripts/run_omy_comparison.py --dataset "$OMY_DATASET" \
  --initial-poses "$OMY_INITIAL" --initialization "$OMY_INIT_KIND" \
  --checkpoint "visual-ft=$OMY_WORK/run-pilot-visual/best.pt" \
  --checkpoint "geometry=$OMY_WORK/run-pilot-geometry/best.pt" \
  --output "$OMY_EVAL/pilot" --execute
```

그다음 temporal cache를 만들고 **visual, geometry, motion 세 모델 모두 같은 temporal cache와 head 학습 일정으로 학습**한다. 이전 구현은 이 단계에서 geometry/motion만 학습했으나, 이제 visual control도 포함한다. teacher-forced previous GT hypothesis이며 실제 prediction을 입력으로 만드는 on-policy 학습은 아니다.

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage motion-prepare --checksums "$OMY_CHECKSUMS" --execute
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage motion --execute
python scripts/run_omy_comparison.py --dataset "$OMY_DATASET" \
  --initial-poses "$OMY_INITIAL" --initialization "$OMY_INIT_KIND" \
  --checkpoint "visual-temporal=$OMY_WORK/run-motion-visual/best.pt" \
  --checkpoint "geometry-temporal=$OMY_WORK/run-motion-geometry/best.pt" \
  --checkpoint "motion=$OMY_WORK/run-motion-motion/best.pt" \
  --output "$OMY_EVAL/temporal" --execute
```

`best.pt`와 `last.pt`를 비교하려면 각 모델을 다른 label로 추가한다. 예를 들어 위 temporal 명령에 `--checkpoint "motion-last=$OMY_WORK/run-motion-motion/last.pt"`를 넣고 새 output을 사용한다. 첫 pilot의 checkpoint 선택 지표는 **9개 validation 시퀀스의 macro mean surface error**로 미리 정한다. A/C 악화나 B의 이득이 숨겨지지 않도록 그룹별 값과 마지막 프레임 오차도 함께 본다. 이는 validation 모델 선택이며 독립 test 결과가 아니다. 반복 선택 후 최종 성능 주장을 하려면 별도 physical-parent test 데이터가 필요하다.

## 8. 결과 파일과 읽는 순서

`comparison.md`: 전체 방법의 all/A/B/C 비교표. error는 mm, threshold 초과율은 %, 프레임 처리 시간은 ms로 표시한다. all은 시퀀스별 평균을 같은 비중으로 평균한다. 긴 clip의 프레임 수로 가중하지 않는다.

`comparison.json`: 같은 요약의 원시 수치. 거리 단위는 m, 시간은 s, 실패 비율은 0~1이다. A/B/C는 시퀀스 이름의 clip 분류이며 frame별 contact/phase나 visibility bucket을 뜻하지 않는다. B/C가 같은 physical parent일 수 있으므로 9개 모두가 통계적으로 독립이라고 간주하지 않는다.

`<label>/<sequence>/run.json`: 초기 pose hash와 초기화 종류, checkpoint hash, pretrained hash, mesh hash/diameter 규약, 입력 manifest/관측 hash, source commit, iteration, 평가점 수를 기록한다. `poses.jsonl`은 추론값만, `frame_metrics.jsonl`은 예측 완료 후 계산한 GT 오차만 담는다. `summary.json`은 초기 오차, 평균·중앙값·95백분위·마지막 오차, diameter 10% 초과 비율을 담는다.

오차는 **선언된 symmetry 변환 중 가장 작은 corresponding surface distance**다. identity만 선언돼 있으면 일반 corresponding-point error다. 최근접점을 찾는 ADD-S도, 표준 BOP AR도 아니다. `failure_fraction_10pct_diameter`는 편의를 위한 프레임 오차 임계 초과율이며 물리적 grasp 실패율이나 자동 tracker failure detector가 아니다.

시간은 frame I/O, FK, crop/render, inference와 GPU 동기화를 포함하며 setup, scoring, 파일 쓰기는 제외한다. 첫 추적 프레임의 warm-up과 OS cache 영향이 있으므로 정밀 GPU kernel benchmark나 보장 FPS로 해석하지 않는다. CPU baseline은 영상 읽기가 없으므로 처리량을 신경망과 같은 연산량으로 비교하지 않는다.

실행 중 실패하면 traceback을 확인하고, 완료되지 않은 작업만 출력된 개별 evaluate 명령으로 새 디렉터리에 실행한다. 이미 완료한 파일을 삭제하지 않는다. suite output에서 아직 생성되지 않은 sequence 경로를 그대로 채운 경우에는 같은 suite 명령에 `--execute` 대신 `--summarize-only`를 붙여 표를 만든다. 서로 다른 초기 pose/geometry/evaluation 규약이나 source commit이 섞이면 합산을 거부한다. 같은 label 안의 checkpoint 설정 및 visual 방법 사이의 pretrained weights/config/refinement 횟수도 검사한다.

## 9. 어떤 결과가 연구 방향을 바꾸는가

kinematic-refine만으로 motion 모델과 비슷하거나 더 좋다면, 우선 단순 baseline을 채택하고 큰 fusion 모델의 필요성을 재검토한다. 추가 신경망이 의미 있으려면 비접촉 가림, slip, release 등 rigid prior가 틀리는 조건에서 더 안정적이라는 근거가 필요하다.

kinematic이 B에서 좋고 A/C에서 나쁘다면, 다음 연구 질문은 “robot 정보를 더 많이 넣을까”보다 **언제 robot motion을 신뢰할까**가 된다. 향후 vision과 proprioception만으로 trust weight를 추정하거나, visual/kinematic 후보 중 residual을 예측하는 작은 모델을 고려할 수 있다. GT contact/phase로 gate를 켠 성능은 별도의 oracle upper-bound 실험으로만 취급한다. 이 gate는 아직 구현되지 않았다.

geometry가 visual-ft보다 좋지만 motion은 더 좋지 않다면, geometry의 가림 해석 이득과 실제 동작 정보의 이득을 분리한다. object-CAD-only, robot state 시간 지연/교란, visibility별 분석은 이후 추가 실험이며 이번 자동 비교에 포함되지 않는다.

좋은 one-step loss에도 rollout이 나쁘면, 더 긴 학습보다 실제 tracker prediction 근방의 hypothesis로 cache를 확장하는 것이 우선 후보다. 아직 fixed teacher-forced cache이며 temporal memory나 sequence loss를 학습한 모델이 아니다.

프로젝트의 의미는 “encoder+fusion을 붙였다”만으로 성립하지 않는다. 가림·접촉 전후에서 단순 기구학보다 나은 **관측 가능한 신뢰 판단**을 보여주고, held-out parent·새 물체·실측 데이터로 일반화까지 확인할 때 더 강해진다. 현재 45개 시퀀스는 이 가설을 판별하는 pilot이고 일반적인 novel-object tracking의 증거는 아니다.

## 10. Compute와 검증 범위

hold/kinematic은 CPU로 실행할 수 있다. visual/kinematic-refine 및 learned rollout은 FoundationPose renderer 때문에 CUDA GPU가 필요하다. 학습 준비 때 확인한 5080 한 대에서 순차 실행하도록 구성했으며 AWS 연결이나 인스턴스는 생성하지 않는다. 정확한 VRAM과 시간은 실측 전이다. batch 4 FP32부터 기존 smoke/tiny gate로 확인한다.

baseline suite는 9개 × 4개 방법이며, learned checkpoint를 하나 추가할 때 9개 rollout이 추가된다. temporal 기본 비교는 7개 방법 × 9개 = 63개 sequence rollout이다. validation 2,382프레임에서 초기화 9개를 제외한 2,373개 frame을 방법별로 추적한다. visual 계열의 기본 iteration은 2이므로 순차 평가 시간이 학습 시간보다 길 수 있다. 먼저 한 B clip으로 실제 시간을 측정한다.

CPU 합성 테스트는 좌표계·입력 누출 방지·파일 출력·집계·경로 이동·diameter 재현성의 논리를 확인한다. 실제 CAD/관절 보정의 정확성, raw dataset checksum, CUDA rendering, 실제 학습 수렴, 5080 VRAM 및 성능 개선은 GPU 머신에서 확인해야 한다. 성공 수치는 실행 후 생성되는 결과만 보고한다.

영상으로 추적을 검사하려면 OMY_TRACKING_VISUALIZATION.md 또는 단일 HTML 21절을 따른다. 저장된 poses.jsonl에서 RGB / 추정+GT / robot FK / 전체 겹침 MP4와 PNG를 생성한다.
