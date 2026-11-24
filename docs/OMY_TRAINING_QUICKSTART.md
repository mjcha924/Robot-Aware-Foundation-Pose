# OMY GPU 학습 실행 가이드

새 OMY measured-state reader와 기존 robot-conditioned refiner를 통합한 작업본이다. 실제 원본 RGB-D와 CUDA 환경에서의 rendering 및 학습은 아직 검증 전이다. 로컬 검증 결과는 별도 테스트 기록을 참조한다.

## 코드 전달

GitHub 별도 브랜치 `feat/omy-training-ready`를 받는다. 5080 실행 명령 전체는 [RUN_ON_5080.md](RUN_ON_5080.md), 학습 원리는 [단일 HTML](OMY_TRAINING_GUIDE.html)을 참조한다.

```bash
git clone --branch feat/omy-training-ready --recurse-submodules https://github.com/mjcha924/Robot-Aware-Foundation-Pose.git omy-training
cd omy-training
```

## 머신과 데이터

기존 FoundationPose가 실행되는 Linux NVIDIA GPU 환경을 사용한다. 5080 16 GB 또는 L40S 한 장, batch 4로 시작한다. Python 3.10 이상 권장. 기존 GPU 환경의 torch/CUDA를 교체하지 않고 다음 추가 의존성을 설치한다.

```bash
python -m pip install -r requirements-training.txt
```

이 명령은 FoundationPose 환경 전체를 설치하지 않는다. 원본 submodule, pretrained weights, mycpp, nvdiffrast와 FoundationPose 의존성이 먼저 필요하다. 설치 절차는 `docs/BASELINE.md` 및 upstream readme를 따른다. Isaac Sim 설치는 학습에 필요하지 않다.

최종 clean dataset 디렉터리와 공식 accepted_checksums.sha256을 캡처 머신에서 가져온다. 이전 accepted/diagnostic 폴더를 사용하지 않는다. 원본 데이터는 읽기 전용으로 유지하고 cache/run은 다른 경로에 저장한다. GitHub clone만으로 RGB-D나 weights를 받을 수 없다.

## 실행 단계

모든 명령은 이 저장소 루트에서 실행한다. 아래 `/data/...`는 GPU 머신의 실제 경로로 바꾼다. `--execute`가 없으면 명령만 출력하며 GPU 작업을 하지 않는다. 어떤 단계도 AWS 자원을 만들지 않는다.

```bash
# 1. 실행 계획만 확인
python scripts/run_omy_training.py --dataset /data/dataset --work /data/omy-training --stage prepare

# 2. 먼저 전체 checksum, CUDA parity와 6개 실제 sample cache 생성
python scripts/run_omy_training.py --dataset /data/dataset --work /data/omy-smoke \
  --stage smoke --checksums /data/accepted_checksums.sha256 --execute

# 3. smoke 통과 후 geometry 및 tiny cache 생성
python scripts/run_omy_training.py --dataset /data/dataset --work /data/omy-training \
  --stage prepare --checksums /data/accepted_checksums.sha256 --execute

# 4. A/B/C 각 16개, 총 48개 예제로 encoder와 fusion만 학습
python scripts/run_omy_training.py --dataset /data/dataset --work /data/omy-training --stage tiny --execute

# 5. 동일 head schedule의 visual-only 및 geometry 비교
python scripts/run_omy_training.py --dataset /data/dataset --work /data/omy-training --stage pilot --execute

# 6. 이전 GT pose에 perturbation을 준 temporal 학습 cache
python scripts/run_omy_training.py --dataset /data/dataset --work /data/omy-motion \
  --stage motion-prepare --checksums /data/accepted_checksums.sha256 --execute

# 7. 같은 temporal cache에서 geometry / motion 비교
python scripts/run_omy_training.py --dataset /data/dataset --work /data/omy-motion --stage motion --execute
```

각 단계의 결과를 확인한 후 다음 단계를 실행한다. `prepare`는 전체 stride-5 cache까지 생성하므로 작은 렌더링만 확인하려면 먼저 단일 시퀀스에 `prepare_robot_refiner.py ... --max-frames-per-sequence 2 --output <새 경로>`를 사용한다. 기존 cache/run 경로는 덮어쓰지 않는다. 중간 실패 후에는 새 work 경로를 선택하거나 출력된 명령 중 아직 실행하지 않은 명령만 새 output 경로로 실행한다.

`tiny`는 heads를 20 epochs 동안 고정한다. train loss의 감소와 encoder/fusion 학습을 확인하는 진단이며 독립 성능 증거가 아니다. `pilot`는 두 방법 모두 heads를 첫 epoch부터 같은 1e-5로 조정한다. 새 branch는 1e-4. 원래 split은 train 36 / validation 9이며 physical-parent overlap을 차단한다.

학습 결과는 `metrics.jsonl`, `run.json`, `best.pt`, `last.pt`에 저장된다. epoch 시간과 CUDA peak allocated memory도 기록한다. 이 값은 cache 생성 시간이나 전체 시스템 GPU 점유량을 포함하지 않는다. 재개는 같은 cache, mode, batch size로 새 output 경로를 사용한다.

```bash
python scripts/train_robot_refiner.py --train /data/omy-training/train \
 --val /data/omy-training/validation --mode geometry --warmup-epochs 0 --epochs 40 \
 --resume /data/omy-training/run-pilot-geometry/last.pt --output /data/omy-training/resumed
```

## Tracking 평가

첫 프레임 pose는 외부 FoundationPose initialization으로 구해 4x4 NumPy 파일로 저장한다. 좌표는 T_camera_raw_mesh다. GT 초기화 진단을 할 경우 별도 표기하고 모든 방법에 동일하게 제공한다.

```bash
python scripts/evaluate_robot_tracker.py /data/dataset/box_B_04 \
 --initial-pose /data/box_B_04_initial.npy \
 --checkpoint /data/omy-training/run-pilot-geometry/best.pt \
 --output /data/results/box_B_geometry
```

checkpoint를 생략하면 동일 bridge의 pretrained visual control이다. 원본 upstream track_one과 완전히 같은 전처리라고 주장하지 않는다. GT는 prediction 후 평가에만 사용하며 current/previous robot state와 RGB-D는 공개 reader로 읽는다. Motion cache는 teacher-forced previous GT supervision이다. 실제 tracker prediction 기반 재학습과 closed-loop rollout 개선은 별도 후속 검증이다.

## 데이터 및 코드 출처

`read_omy_tracking_sample.py`, `omy_robot_surface.py`, `omy_kinematics.py`는 동일 프로젝트 데이터 브랜치 c23b37976ed1ad3d5f48022fd071d2fa49e21a00에서 가져왔다. 모델 입력은 canonical robot 총 512점 + object CAD 256점, 11 channels다. 새 reader는 정답 link pose 대신 measured joint FK를 사용한다. 현재와 이전 표면점을 동일 현재 카메라 좌표로 표현하고 timestamp 차이로 속도를 계산한다.

Frozen encoder cache는 hypothesis에 의존한다. geometry와 motion 학습에 다른 hypothesis를 사용하면 별도 cache를 생성해야 한다. Dataset 확인과 GPU preflight를 통과하지 않은 상태를 학습 준비 완료로 간주하지 않는다.
