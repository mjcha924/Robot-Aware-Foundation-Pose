# 5080 컴퓨터에서 첫 학습 실행

대상은 Linux와 NVIDIA GPU다. 아래 명령은 **5080에서 원본 FoundationPose가 작동하는 Python 또는 컨테이너 환경** 안에서 실행한다. Isaac Sim이 실행된다는 것만으로는 이 조건을 만족하지 않는다. CUDA 11.8/PyTorch 2.0의 옛 3070 환경을 5080에 그대로 복사하지 않는다. Blackwell 지원 PyTorch/CUDA 및 native extension 조합을 먼저 검증한다. [PyTorch Blackwell 지원 안내](https://pytorch.org/blog/pytorch-2-7/).

현재 이 브랜치의 실제 5080 검증은 아직 전이다. 환경이 없다면 upstream 설치 안내와 `docs/BASELINE.md`의 의존성 목록을 참고하되, 그 문서의 옛 버전 조합은 5080용 설치 처방이 아니다. 새 환경이 실제 rendering gate를 통과할 때까지 학습을 진행하지 않는다.

**리뷰 수정 이후에는 기존 cache를 재사용하지 않는다.** diameter 규약이 바뀌었으므로 새 OMY_WORK에서 smoke/cache 생성부터 진행한다. 학습 없는 기구학 baseline과 전체 비교 순서는 OMY_MOTION_BASELINE_EXPERIMENTS.md 및 HTML 17~20절에 있다.

## 1 코드 받기

기존 작업과 충돌하지 않도록 새 디렉터리에 받는다. private repository라면 GPU 머신의 GitHub 인증을 사용한다.

```bash
git clone --branch feat/omy-training-ready --recurse-submodules \
  https://github.com/mjcha924/Robot-Aware-Foundation-Pose.git omy-training
cd omy-training
git status --short --branch
```

## 2 GPU와 Python 확인

원래 FoundationPose가 동작하는 환경을 활성화한 뒤 실행한다. 컨테이너라면 저장소와 dataset 경로를 컨테이너 안에서 접근할 수 있게 mount해야 한다. 호스트의 경로를 컨테이너 경로와 혼동하지 않는다.

```bash
nvidia-smi
python -c "import torch; print('torch',torch.__version__,'cuda',torch.version.cuda); assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0)); x=torch.randn(64,64,device='cuda'); print((x@x).mean().item())"
python -m pip install -r requirements-training.txt
```

이 requirements는 추가 reader/test 의존성이다. torch나 전체 FoundationPose 환경을 설치하지 않는다. pretrained weights는 별도 준비하며 `third_party/FoundationPose/weights/`의 upstream 지정 구조를 따른다. 코드 저장소에는 weights가 없다.

## 3 데이터와 출력 경로 지정

아래 DATASET은 캡처 머신에 기록된 경로다. 다른 컴퓨터로 옮겼거나 컨테이너 안에서 실행하면 반드시 수정한다. 최종 `dataset` 디렉터리와 공식 checksum 파일을 함께 가져와야 한다. 데이터 디렉터리 이름은 checksum의 `dataset/...` 상대 경로와 맞춘다.

```bash
export OMY_DATASET=/home/a09/mj-projects/omy-tracking-dataset/outputs/omy_pilot/dataset
export OMY_CHECKSUMS=/home/a09/mj-projects/omy-tracking-dataset/outputs/omy_pilot/accepted_checksums.sha256
export OMY_WORK="$PWD/outputs/omy_training_002"
test -d "$OMY_DATASET"
test -f "$OMY_CHECKSUMS"
python scripts/check_omy_training_readiness.py --dataset "$OMY_DATASET"
```

점검 도구의 exit 0은 학습 준비 완료를 뜻하지 않는다. 뒤의 CUDA/실제 rendering gate가 필요하다. `OMY_WORK`는 새 경로로 정하며 기존 실행 결과를 덮어쓰지 않는다.

## 4 실행 계획 확인

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage smoke
```

`--execute`가 없으므로 어떤 학습이나 GPU 작업도 하지 않는다.

## 5 첫 GPU 검증

전체 공식 checksum 검증 → 원본 출력 일치와 gradient 검사 → A/B/C 각 2개 실제 sample cache 생성 순서다. 최대 6개 sample이 만들어진다. smoke-train/manifest.json의 실제 수를 확인하고 더 적다면 건너뛴 hypothesis 원인을 확인한다. 자동 검사는 이미지 overlay를 사람이 검토한 것을 대신하지 않는다.

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage smoke --checksums "$OMY_CHECKSUMS" --execute
```

오류가 나면 여기서 멈추고 마지막 traceback을 확인한다. 원본 weights, native extension, CUDA 오류를 무시하고 학습 단계로 넘어가지 않는다.

smoke 성공 후 학습에 앞서 HTML 19절의 hold/kinematic/visual/kinematic-refine 비교를 먼저 실행하는 것을 권장한다.

## 6 학습 cache 준비

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage prepare --checksums "$OMY_CHECKSUMS" --execute
```

출력은 train 1,926개, validation 478개, tiny-train 최대 48개다. 현재 perturbation 설정에서 카메라 뒤쪽 hypothesis는 건너뛰므로 실제 수는 이보다 작을 수 있다. 이 단계는 학습이 아니라 rendering과 frozen feature 추출이다.

Tiny, pilot, motion은 독립적인 비교 실험이며 이전 단계 checkpoint를 자동으로 이어받지 않는다. 명시적인 --resume만 학습을 재개한다.

## 7 처음 하는 작은 학습

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage tiny --execute
```

48개 이하 sample, batch 4, 20 epochs. visual encoder와 pose heads를 고정하고 robot encoder와 fusion만 학습한다. `run-tiny-geometry/metrics.jsonl`의 train error가 감소하는지 확인한다. 줄지 않으면 전체 학습으로 확대하지 않는다. validation 개선은 이 overfit 진단의 필수 조건이 아니다.

```bash
tail -n 5 "$OMY_WORK/run-tiny-geometry/metrics.jsonl"
```

학습 곡선은 TensorBoard로도 볼 수 있다. 각 run 폴더의 `tensorboard/`에 기록하며 `metrics.jsonl`이 여전히 기준 기록이다. 기록하지 않으려면 `train_robot_refiner.py`에 `--no-tensorboard`를 준다.

```bash
tensorboard --logdir "$OMY_WORK" --port 6006
# 브라우저에서 http://localhost:6006
```

`epoch/*`의 x축은 metrics.jsonl과 같은 0부터 시작하는 epoch, `step/*`은 optimizer update 횟수다. `model/residual_scale_alpha`는 모든 sample이 공유하는 fusion scalar이며 접촉 확률이 아니다.

## 8 같은 조건으로 비교 학습

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage pilot --execute
```

visual-only와 geometry를 순차 학습한다. 같은 cache/seed와 heads 학습 일정을 사용한다. 새 encoder/fusion 학습률은 1e-4, heads는 1e-5, 20 epochs다. epoch 출력은 0부터 시작한다. `best.pt`는 validation surface error가 가장 낮았던 checkpoint, `last.pt`는 마지막 epoch checkpoint다.

## 9 그다음 motion 비교

처음 학습이 확인된 뒤에만 진행한다. 이전 GT pose를 현재 카메라 좌표로 변환하고 perturbation을 더한 hypothesis를 사용하는 teacher-forced 학습이다.

```bash
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage motion-prepare --checksums "$OMY_CHECKSUMS" --execute
python scripts/run_omy_training.py --dataset "$OMY_DATASET" \
  --work "$OMY_WORK" --stage motion --execute
```

동일 temporal cache에서 visual, geometry, motion 세 모델을 학습해 비교한다. 이 단계는 실제 tracker prediction을 사용한 on-policy 학습이 아니다. tracking rollout으로 별도 검증해야 한다.

## 10 중단과 재개

각 epoch 끝에 저장한다. 실행 중 Ctrl+C로 중단하면 현재 epoch 중간 상태는 저장되지 않을 수 있다. 같은 cache/mode/batch/warmup 설정을 유지하고 새 output 폴더에서 재개한다. 아래는 geometry pilot을 총 40 epochs로 연장하는 예시다.

```bash
python scripts/train_robot_refiner.py \
  --train "$OMY_WORK/train" --val "$OMY_WORK/validation" \
  --mode geometry --batch-size 4 --warmup-epochs 0 --epochs 40 \
  --resume "$OMY_WORK/run-pilot-geometry/last.pt" \
  --output "$OMY_WORK/run-pilot-geometry-resumed"
```

같은 orchestrator 명령을 다시 실행하면 기존 output 보호 때문에 실패할 수 있다. 실패한 단계만 출력된 개별 명령으로 새 output에 실행하거나 새 OMY_WORK로 처음부터 실행한다. 기존 cache/run을 지우는 방식으로 해결하지 않는다.

자세한 학습 원리와 파일별 설명은 `docs/OMY_TRAINING_GUIDE.html`을 브라우저에서 연다. HTML은 인터넷 없이 읽을 수 있으며 외부 자료 링크만 네트워크를 사용한다.
