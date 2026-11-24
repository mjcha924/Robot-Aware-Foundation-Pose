# OMY 첫 학습 준비 계획

2026년 11월 24일 확인. 첫 목표는 frozen FoundationPose에 robot encoder와 residual cross-attention을 연결해 실제 OMY 데이터로 작은 학습을 완료하는 것이다. 기존 5080을 우선 사용하고, CUDA 호환성 또는 사용 일정 때문에 필요할 때 AWS 단일 L40S로 옮긴다. 이 준비에는 서버 생성, 데이터 업로드, 학습 실행이 포함되지 않는다.

## 확인된 출발점

- 데이터 브랜치 `feature/omy-tracking-dataset`: `c23b37976ed1ad3d5f48022fd071d2fa49e21a00`.
- 원격 main: `bcae895e3bfd64dc7b14627212ca767a7d92cc98`. 데이터 작업은 main에 합쳐져 있지 않다.
- 로컬 모델 브랜치 `feat/robot-conditioned-refiner`: `857d0b43f486f4ab5288d08cbddad7a34cbcaf01`. 조회된 원격 브랜치 목록에는 이 모델 브랜치가 없다.
- 최종 데이터: 45개 시퀀스, train 36개 9,617프레임, validation 9개 2,382프레임. 총 11,999프레임, 30 Hz.
- RGB-D 원본은 Git 밖에 있다. 논리 크기 7.543 GB, hardlink 보존 시 3.597 GB. Git clone만으로 받을 수 없다.
- 캡처 머신의 기록된 원본 위치: `/home/a09/mj-projects/omy-tracking-dataset/outputs/omy_pilot/dataset/`.
- 현재 Mac 작업 폴더에는 원본 데이터가 없고, 기본 python3에 torch/numpy가 없다. NVIDIA CUDA 검증 환경이 아니다. AWS CLI도 PATH에서 확인되지 않았다. 계정 인증이나 서버 연결은 시도하지 않았다.

근거: [고정된 인계 문서](https://github.com/mjcha924/Robot-Aware-Foundation-Pose/blob/c23b37976ed1ad3d5f48022fd071d2fa49e21a00/docs/omy_tracking/PIPELINE_HANDOVER.md), [데이터 목록](https://github.com/mjcha924/Robot-Aware-Foundation-Pose/blob/c23b37976ed1ad3d5f48022fd071d2fa49e21a00/docs/omy_tracking/evidence/dataset_manifest.json).

## 첫 실행 전 구현할 변경

1. 별도 통합 브랜치에서 데이터 reader와 로컬 모델 변경을 함께 가져온다. 기존 두 브랜치를 덮어쓰거나 upstream FoundationPose를 수정하지 않는다. GPU 머신에는 데이터 브랜치만 받으면 학습 코드가 없다는 점에 유의한다.
2. 새 OMY reader 어댑터를 추가한다. 기존 `IsaacSequence.points()`는 GT link pose를 읽으므로 실제 학습 경로를 `read_tracking_input → measured joints → FK → robot_surface_pair`로 교체한다. GT pose는 별도 target reader에서만 읽는다.
3. 새 surface의 `motion_camera_m`은 변위다. timestamp 차이로 나눠 속도로 바꾸고, 기존 11-channel 규약에 맞춘다. 동일 canonical surface samples를 시퀀스 내 재사용한다. pose hypothesis 좌표 변환, 법선 회전, 물체 크기 정규화, root/raw-mesh/centered-mesh 변환을 명시적으로 검증한다.
4. 링크당 1,024점을 무조건 모델에 넣지 않는다. 첫 실험은 기존 규모인 robot 전체 512점과 CAD 256점을 기준으로 고정된 샘플링을 적용한다. 손가락과 물체 주변을 충분히 표현하는지 overlay로 확인하고 점 수 증가는 이후 ablation으로 다룬다.
5. manifest의 split/parent_group으로 학습 목록을 만든다. 현재 cache hash 검사만으로는 서로 다른 B/C clip의 동일 physical parent를 잡아내지 못한다. parent가 train/validation을 넘지 않도록 별도 검사를 추가한다.
6. 작은 학습용 sample 제한, 고정 heads 설정, 시간/peak GPU memory/gradient 기록을 추가한다. 현재 CLI의 warmup_epochs를 전체 epochs 이상으로 두면 heads를 계속 고정할 수 있지만, 학습 중인 파라미터 목록도 출력한다. tiny overfit은 train loss로 판단하고 validation은 독립적으로 유지한다.
7. geometry pilot 이후 previous-pose hypothesis와 train tracker rollout 기반 cache를 추가한다. hypothesis를 바꾸면 렌더링과 visual cache도 다시 생성한다. motion 채널을 켜는 것만으로 시간축 학습이 구현되는 것은 아니다.

## 단계별 실행과 통과 조건

| 단계 | 범위 | 산출물과 통과 조건 |
|---|---|---|
| 데이터 전달 | 최종 dataset과 공식 checksum 파일 | 전체 checksum 통과, 원래 36/9 및 parent split 유지 |
| CUDA 확인 | 원본 weights, native extension, 한 프레임 rendering | 기존 parity checker 통과, 실제 RGB-D와 CAD/FK overlay 확인 |
| 첫 학습 | A/B/C train에서 합계 32~64 sample, geometry mode, batch 4 | encoder와 fusion gradient가 유한하고 train pose loss 감소, checkpoint 재로딩 일치 |
| baseline 진단 | validation 9개, 필요하면 전체 45개 | 원본 tracking의 A/B/C 및 가림별 오류, 초기화 실패 별도 기록 |
| geometry pilot | stride 5, train 1,926 / validation 478 sample, 20 epochs 출발 | visual-only와 geometry를 동일 sample/seed/head schedule로 비교 |
| motion pilot | 이전 pose 기반 hypothesis를 포함한 별도 cache | geometry 대비 motion 추가 효과와 state 지연/교란 영향 확인 |
| 연속 평가 | 동일 초기 pose에서 모든 프레임 prediction 누적 | CAD surface error, 위치/회전 오차, 실패율, 가림 후 복구 시간, 추론 시간 |

첫 tiny 학습은 heads를 고정하고 encoder+fusion을 함께 학습한다. 전체 pilot에서는 두 방법 모두 처음부터 heads를 같은 작은 학습률로 학습시키는 등 head schedule을 맞춘다. 현재 trainer는 visual mode의 heads를 즉시 학습하고 robot mode는 warmup 후 학습하므로 기본값 그대로의 비교에는 이 차이가 있다. visual-only는 robot CAD branch까지 제거한 비교다. Geometry 효과가 나타나면 object-CAD-only 대조군을 추가하여 robot state와 추가 CAD 표현의 효과를 분리한다.

C는 부분 가림 상태로 시작하므로 GT 초기화 진단과 실제 FoundationPose 초기화를 분리한다. GT 초기화는 모든 방법에 동일하게 주고 명시한다. 이후에는 prediction만 전달한다. oracle mask도 모든 방법에 동일한 조건으로 제공하며 별도 표기한다. held-out 9개는 validation이고 독립 최종 test가 아니다. 세 물체만으로 novel-object 일반화를 주장하지 않는다.

## Compute 계획

다음은 아직 측정하지 않은 시작 설정이다. full FoundationPose 재학습이 아니라 frozen visual features와 작은 robot/fusion branch의 학습이다. Isaac Sim은 기존 데이터를 읽고 학습하는 데 필요 없다.

| 자원 | 시작 설정 |
|---|---|
| GPU | 기존 RTX 5080 16 GB 한 장 우선, batch 4, FP32, 렌더링과 cached training 분리 |
| RAM | 32 GB 출발, 데이터 로딩과 cache가 병목이면 64 GB |
| 디스크 | 데이터/cache/결과용 가용 공간 50 GB 목표. 새 AWS 머신은 이미지·weights·build 여유를 포함해 150 GB EBS를 계획값으로 잡고 실제 사용량으로 조정 |
| AWS 대안 | g6e.xlarge: L40S 48 GB 1장, 4 vCPU, RAM 32 GiB. CPU 준비가 병목이면 g6e.2xlarge: 같은 GPU, 8 vCPU, RAM 64 GiB |
| 다중 GPU | 첫 pilot에는 도입하지 않음 |

5080에서 Isaac Sim 캡처가 성공한 것과 FoundationPose/PyTorch/native extension 호환성은 별개다. 현재 정상 동작하는 FoundationPose 환경이 있으면 먼저 재사용한다. GPU/드라이버 확인 뒤 nvdiffrast, mycpp 등의 실제 import와 rendering을 검증한다. DLAMI에 PyTorch가 있다는 사실만으로 준비 완료로 판단하지 않는다. 모델 명칭이 아니라 실제 AMI ID/아키텍처/패키지 버전을 기록한다.

AWS 사양 근거: [공식 G6e 사양](https://aws.amazon.com/ec2/instance-types/g6e/). 리전과 구매 방식이 정해지지 않아 실제 단가 및 현재 크레딧 잔액은 확인하지 않았다.

## 시간과 비용 산정 방법

먼저 100개 cache sample과 warmup 이후 100 training batch, validation batch를 실제 GPU에서 측정한다. GPU 연산 전후 synchronize하고 데이터 로딩 포함 wall time과 peak allocated/reserved VRAM을 기록한다. cache bytes/sample도 측정한다.

stride 5와 hypothesis 1개/frame이면 총 2,404 samples. batch 4이면 epoch당 train 482 batches와 validation 120 batches, 20 epochs에서 train 9,640과 validation 2,400 batches다.

`총 시간 = 2404 × cache초/sample + 9640 × train초/batch + 2400 × validation초/batch`

순수 계산 예시로 cache 0.5초/sample, train 0.2초/batch, validation 0.1초/batch를 대입하면 한 모델의 cache+20 epochs는 약 0.94시간이다. 세 값은 측정치나 성능 예측이 아니다. 설치·전송·baseline·시퀀스 평가·실패 재시도는 별도다. 세 모델의 실험은 공유 cache 비용을 한 번만 포함하고 각 training/validation 시간을 더한다.

첫 유료 세션은 환경 준비 후 2 GPU-hour의 작은 작업 범위를 계획하고 실제 throughput으로 다음 범위를 정한다. 자동 종료나 요금 상한을 설정했다는 뜻은 아니다. 예를 들어 가정 단가가 $2/hour일 때 10시간은 compute $20, 30시간은 $60이며 EBS·전송 등은 별도다. 실제 견적은 AWS 리전 단가로 교체한다. 과거 언급된 $450 크레딧의 현재 잔액/만료/적용 조건은 미확인이다.

## 준비 도구 사용

저장소 루트에서 아래 점검은 파일을 수정하거나 AWS에 연결하거나 학습을 시작하지 않는다.

```bash
python3 scripts/check_omy_training_readiness.py
python3 scripts/check_omy_training_readiness.py --dataset /actual/path/to/dataset
```

GPU 측정값이 생긴 후 다음 인자에 값을 넣으면 예상 시간을 계산한다. 아래 숫자는 위의 가상 예시다.

```bash
python3 scripts/check_omy_training_readiness.py \
  --cache-seconds-per-sample 0.5 --train-seconds-per-batch 0.2 \
  --val-seconds-per-batch 0.1 --usd-per-hour 2
```

이 도구는 metadata/경로 존재 확인과 산술 계산만 한다. exit 0도 학습 준비 완료를 의미하지 않는다. 원본 checksum 검증, 실제 CUDA parity, 새 reader 통합과 tiny optimization은 별도 gate다.

## AWS를 사용할 경우 실행 직전 필요한 정보

기존 5080의 사용 가능 여부와 FoundationPose 실행 환경, 최종 dataset의 접근 가능한 경로가 우선이다. AWS가 필요해지면 리전, 기존 인스턴스 유무, 접속 방식, GPU quota, 실제 AMI와 시간당 가격을 확인한 뒤 실행한다. 로컬 V1과 데이터 reader를 합친 코드 전달이 먼저다. 인증 키는 코드나 문서에 저장하지 않는다. 체크포인트는 영속 디스크에 저장하고 장시간 무인 작업 전에 resume를 검증한다.

현재는 manifest snapshot, 점검 도구와 실행 계획만 준비했다. 모델/reader 통합, 패키지 설치, 원본 데이터 전송, AWS 자원 생성 및 학습은 수행하지 않았다.
