# 추적 결과를 영상으로 확인하기

`visualize_robot_tracker.py`는 저장된 추정 pose를 RGB에 투영하고, 물체 GT와 측정 관절값 기반 로봇 FK를 겹쳐 보여주는 **추론 후 진단 도구**다. 기존 추적 결과를 다시 학습하거나 수정하지 않는다. CPU에서 실행하며 FoundationPose weights와 CUDA renderer가 필요 없다. 현재 OMY packaged sequence를 지원한다.

## 1. 화면과 색상 읽기

기본 출력은 네 칸이다. 좌측 위는 원본 RGB, 우측 위는 추정 pose + GT, 좌측 아래는 로봇 FK, 우측 아래는 세 가지를 모두 겹친 화면이다. 각 화면에서 같은 프레임을 동시에 비교할 수 있다.

**청록색 P:** 저장된 추정 `T_camera_raw_mesh`에 물체 CAD를 놓는다. 물체의 mesh edge 일부와 실선 bounding box, `P:X/Y/Z` 축을 표시한다. bounding box는 raw mesh 좌표계에서 만든 3D box이며 매 프레임 영상에서 다시 맞춘 2D box가 아니다.

**분홍색 G:** GT pose에 같은 CAD를 놓고 점선 box와 `G:X/Y/Z` 축을 표시한다. GT는 `inverse(T_world_camera) · T_world_object_gt · T_object_mesh`로 raw mesh 좌표에 맞춘다. 정확히 겹치면 일부 선이 가려질 수 있으므로 점선 box와 별도 RGB 화면을 함께 본다.

**노란색 E / 로봇 선:** 로봇 link mesh를 현재 measured joint positions와 joint inventory의 FK로 변환한다. `E:X/Y/Z`는 기본값 `link6`의 좌표축이다. simulator의 정답 link transform은 사용하지 않는다. 로봇의 전체 geometry link는 함께 표시한다.

상단에는 frame ID, 첫 프레임 대비 시간, 색상 범례가 나온다. `run.json`이 함께 있으면 방법명·학습 모드·`oracle-first-frame` 또는 `external` 초기화 종류도 표시한다. frame 0은 `INITIAL POSE`로 표시한다. 출처 정보가 없는 수입 pose 파일은 초기화 종류를 확인하지 못했다는 문구가 나온다.

이 영상은 **X-ray 진단 표시**다. 카메라 뒤쪽과 화면 밖의 선은 잘라내지만, 물체나 로봇에 가려진 표면은 숨기지 않는다. 노란 선이 물체를 관통해 보인다고 곧바로 충돌이나 FK 오류로 판단하면 안 된다. 일부 edge만 고정 선택해 그리므로 완전한 mesh silhouette나 pixel mask가 아니다. 시각화는 자동 정확도 평가를 대체하지 않는다.

## 2. 코드와 영상 저장 의존성 준비

기존 clone에서 변경사항을 저장한 뒤 같은 브랜치의 최신 코드를 받는다. Python은 기존 학습 환경을 사용한다. CPU 전용 환경이라면 torch와 `requirements-training.txt`의 reader 의존성을 먼저 준비한다. 이 추가 requirements는 torch/CUDA를 교체하지 않는다.

```bash
git switch feat/omy-training-ready
git pull --ff-only origin feat/omy-training-ready
python -m pip install -r requirements-visualization.txt
```

추가 패키지 `imageio-ffmpeg`는 CPU MP4 저장용이다. FFmpeg를 사용할 수 없거나 설치하고 싶지 않으면 아래 명령에 `--png-only`를 붙이면 된다. 이 경우 선택한 모든 프레임을 PNG로 저장하고 MP4는 만들지 않는다.

## 3. 한 시퀀스의 추적 결과 시각화

앞선 비교 실험에서 만든 `poses.jsonl`을 입력으로 사용한다. 아래 예시는 HTML 19절의 pilot 비교가 끝난 상태에서 `box_B_04` geometry 모델 결과를 시각화한다. `OMY_DATASET`, `OMY_EVAL`은 해당 실험의 실제 경로여야 한다.

```bash
python scripts/visualize_robot_tracker.py "$OMY_DATASET/box_B_04" \
  --poses "$OMY_EVAL/pilot/geometry/box_B_04/poses.jsonl" \
  --output "$OMY_EVAL/videos/geometry-box-B"
```

학습 없이 만든 baseline 결과를 먼저 보려면 다음을 실행한다.

```bash
python scripts/visualize_robot_tracker.py "$OMY_DATASET/box_B_04" \
  --poses "$OMY_EVAL/pretrained-baselines/kinematic-refine/box_B_04/poses.jsonl" \
  --output "$OMY_EVAL/videos/kinematic-refine-box-B"
```

`--poses`는 checkpoint 파일이 아니라 **추적이 이미 끝난 pose 기록**이다. 아직 추적하지 않았다면 19절의 `evaluate_robot_tracker.py` 또는 `run_omy_comparison.py`를 먼저 실행한다. 예측이 올바른지 검사하기 위한 영상이지 새 prediction을 생성하는 명령이 아니다.

## 4. 출력 파일 열기

`overlay.mp4`를 일반 동영상 플레이어에서 연다. 기본은 패널당 최대 640px인 네 칸 영상이며 원본보다 확대하지 않는다. `preview.png`는 선택한 첫 프레임의 동일한 그림이다.

`frames.jsonl`에는 출력 영상의 프레임 순서와 원본 `frame_index`/`frame_id`, 관측 timestamp, 영상 시간이 대응돼 있다. 그려진 box/robot edge 수가 0이면 화면 밖 또는 카메라 뒤쪽에 pose가 있는지 확인한다. 이 수치는 visibility fraction이나 정확도 점수가 아니다.

`visualization.json`에는 입력 pose·관측·joint inventory·GT·mesh hash, 사용한 구간/stride, 영상 크기/FPS와 출처 확인 결과를 기록한다. 같은 폴더의 `run.json`이 있으면 sequence와 기록된 입력 hash, object mesh가 맞는지 먼저 확인한다. 다르면 섞인 결과를 그리는 대신 중단한다. `run.json`이 없으면 frame 순서·수·pose 형식은 검사하되 provenance는 `unverified`로 기록한다. pose가 좋은지 나쁜지의 판정과는 다르다.

출력은 새 디렉터리에만 생성한다. 기존 결과와 raw dataset 안에는 덮어쓰지 않는다. RGB 원본, GT, 예측 pose와 모델 가중치는 변경하지 않는다.

## 5. 짧은 구간·한 화면·정지 이미지

먼저 30~89번 프레임을 2프레임 간격으로 확인하는 예시다. `--start`는 포함하고 `--stop`은 포함하지 않는다. frame ID가 아니라 관측 배열의 0부터 시작하는 index다. `--stride 2`는 30Hz 원본에서 15FPS로 저장하므로 움직임을 두 배 빠르게 재생하지 않는다.

```bash
python scripts/visualize_robot_tracker.py "$OMY_DATASET/box_B_04" \
  --poses "$OMY_EVAL/pilot/geometry/box_B_04/poses.jsonl" \
  --output "$OMY_EVAL/videos/geometry-box-B-detail" \
  --start 30 --stop 90 --stride 2 --save-frames
```

`--save-frames`는 MP4와 함께 `frames/000030.png`처럼 원본 index 이름의 정지 이미지를 저장한다. 번호가 건너뛰는 것은 stride 때문이다. 짧은 구간을 고를 때는 영상의 t=0이 원본 clip의 t=0과 다를 수 있으므로 화면의 시간과 mapping 파일을 함께 확인한다.

보고서용으로 전체 겹침 한 화면만 만들거나 더 크게 보고 싶을 때는 다음 옵션을 사용한다.

```bash
python scripts/visualize_robot_tracker.py "$OMY_DATASET/box_B_04" \
  --poses "$OMY_EVAL/pilot/geometry/box_B_04/poses.jsonl" \
  --output "$OMY_EVAL/videos/geometry-box-B-overlay" \
  --layout overlay --panel-width 960
```

카메라 내참수 K도 RGB의 축소 비율과 pixel-center 위치에 맞춰 함께 변환한다. H.264 영상 크기는 필요한 경우 가장자리에 1px을 덧붙여 짝수로 만들며, 16배수 크기를 맞추기 위해 영상을 임의로 늘리지 않는다.

느리거나 선이 너무 복잡하면 `--object-edges 256 --robot-edges-per-link 64`로 줄일 수 있다. 기본은 물체 512개 edge, 로봇 link당 128개 edge다. edge 샘플은 프레임마다 바뀌지 않는다. mesh edge를 줄여도 box와 좌표축은 유지한다.

## 6. GT가 없거나 추적이 중간에 멈췄을 때

실제 관측처럼 GT가 없으면 `--no-gt`를 명시한다. GT pose와 GT hash를 읽지 않고 추정 pose와 robot FK만 그린다. `run.json`의 GT hash 확인도 생략하며 출처 기록에 표시한다. 잘못된 GT 파일을 조용히 숨기는 기본 동작은 없다.

추적 중 오류로 `poses.jsonl`이 앞부분만 저장됐으면 `--allow-partial`을 추가한다. **frame 0부터 연속으로 정렬된 prefix만** 허용한다. 중간 frame 누락, 순서 뒤바뀜, 잘못된 frame ID는 이 옵션으로 무시하지 않는다. partial 결과임을 metadata에 기록하며 전체 성능 평가로 취급하지 않는다.

```bash
python scripts/visualize_robot_tracker.py "$OMY_DATASET/box_B_04" \
  --poses "$OMY_EVAL/interrupted-run/poses.jsonl" \
  --output "$OMY_EVAL/videos/interrupted-debug" \
  --allow-partial --png-only
```

## 7. 무엇을 먼저 볼까

A에서는 물체가 정지해 있는데 추정 pose만 로봇을 따라 움직이는지 본다. B에서는 grasp 이후 물체 회전과 이동을 함께 따라가는지, 가림 중 drift가 커지는지 확인한다. C에서는 release 후에도 물체를 로봇에 붙어 있는 것으로 추정하는지 본다. 이 분류는 화면 해석 가이드이며 모델 입력에 접촉 정답을 넣는다는 뜻이 아니다.

로봇 FK가 RGB의 로봇과 계속 어긋나면 먼저 camera/base calibration, joint 순서와 단위, timestamp를 점검한다. 추정과 GT가 모두 물체에서 같은 방향으로 어긋나면 raw mesh/object-root/centered mesh 변환과 K를 점검한다. GT만 잘 맞고 추정이 시간이 지날수록 어긋나면 tracking drift 가능성을 본다. 정확한 원인 판정에는 pose 기록과 수치 평가도 함께 필요하다.

현재 검증은 합성 scene에서 투영·near-plane clipping·움직이는 FK·GT mesh offset·프레임 정렬·PNG 저장·실제 MP4 encode/decode를 확인한 것이다. 실제 OMY RGB와의 정합이나 학습 성능은 GPU 머신에서 만든 추적 결과로 확인해야 한다. 이번 시각화 추가 때문에 학습 cache를 다시 만들 필요는 없다. 앞서 diameter 규약이 바뀌기 전의 cache를 새로 만들어야 한다는 규칙은 그대로다.
