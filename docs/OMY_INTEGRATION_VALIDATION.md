# OMY 통합 검증 기록

2026년 11월 24일 로컬 CPU 검증: `88 passed, 1 skipped`. 격리된 임시 Python 3.9 환경, torch 2.8.0, numpy 2.0.2, scipy 1.13.1을 사용했다. 이는 GPU 환경 dependency lock이 아니다.

기존 테스트는 surrogate encoder를 통한 gradient, 작은 학습, checkpoint 및 resume를 포함한다. 추가 테스트는 실제 FK 코드에 합성 관절 inventory/mesh를 제공하여 다음을 확인한다.

- GT 파일이 없어도 OMY adapter 구성, RGB-D 읽기, 768×11 point feature 생성 가능.
- 현재/이전 동일 표면점에서 비영 속도 생성, frame 0에서도 preroll 관측 사용.
- 반복 reader 생성 시 canonical/CAD 샘플 일치.
- GT frame 순서 불일치 거부.
- train/validation physical-parent overlap 거부.
- 잘못된 checksum 및 dataset 밖 경로 거부.

CLI smoke/motion 실행 계획 출력과 Python 구문 검사, git diff whitespace 검사도 통과했다. 실제 OMY payload checksum, FoundationPose CUDA parity/rendering, 실제 데이터 tiny overfit, 5080/L40S 호환성 및 throughput은 GPU 머신의 다음 검증 단계다. 자동 실행기는 이를 우회하지 않고 실패 시 중단한다.

코드는 feat/omy-training-ready 브랜치에 배포한다. AWS 생성/연결과 실제 데이터 학습은 수행하지 않았다. 기존 OMY_FIRST_TRAINING_PLAN.md는 통합 전 계획 기록이며 현재 실행법은 OMY_TRAINING_QUICKSTART.md를 따른다.

## 리뷰 수정 및 baseline 회귀 검사

- pretrained weight 경로 이동 허용; config 의미/weight 내용 차이는 거부. 구형 geometry cache 거부.
- 정확한 vertex diameter가 RNG/vertex 순서에 독립적. 평면/선 mesh도 검사.
- dense 평가점 샘플링은 global RNG와 독립적.
- rigid-grasp 회전 lever arm, 이동 camera 보상, 고정 tool offset 상쇄.
- repeated refinement에서 JSON/이미지 재읽기 및 FK 중복 없음; 이전 base pose 이동 반영.
- GT 없는 합성 OMY로 다섯 방법의 동일 초기화·frame당 prior 한 번 적용 검사.
- CPU evaluator 실제 파일 저장부터 dense scoring/summary까지 검사. 해당 최소 fixture는 전체 export schema 검사를 별도 mock하고, schema 자체는 기존 validator 테스트로 검사.
- 초기 프레임 제외, macro average 및 비교 초기화/반복 횟수/모델 설정 불일치 거부.

이 검증은 GPU에서 원본 FoundationPose를 실제로 돌린 검증이 아니다. CUDA gate 한 개는 CPU 환경 때문에 skip했다. 실험 명령과 HTML은 최신 규약으로 갱신했다.

HTML은 26개 절로 확장했으며 desktop/mobile 가로 넘침, 학습 단계 버튼, 계산기, JavaScript 오류와 신규 실험 명령 포함 여부를 확인했다. `python scripts/build_omy_training_guide.py`로 문서 소스에서 재생성할 수 있다.

## 추적 시각화 검증

추가 9개 테스트는 OpenCV 좌표계 투영, 화면/near-plane clipping, GT object-root → raw mesh offset, 측정 FK와 simulator link GT 분리, prediction frame 순서/부분 결과 검사, provenance 불일치, PNG 저장과 입력 보존, no-GT 모드, 실제 CPU MP4 encode/decode를 포함한다. MP4 검사에는 임시 환경의 imageio-ffmpeg 0.6.0을 사용했다. `requirements-visualization.txt`를 설치하지 않으면 MP4 테스트는 별도 skip될 수 있다. 실제 OMY 데이터 overlay 정합은 아직 확인 전이다.

## 입문 설명과 정확성 검토

2026-11-24: 학습/모델 코드를 변경하지 않고 HTML 22~26절을 보완했다. Pose 좌표계와 decoder, scalar SGD 숫자 예제, 실제 loss·AdamW 설정, frozen/eval/dropout, mixed robot+CAD tokens, 독립 실험과 resume, checkpoint 구성은 현재 소스와 대조했다. 원론은 FoundationPose·PointNet++·Attention 논문, Modern Robotics, PyTorch 2.8 공식 문서를 확인했다. 실제 학습/GPU 결과는 추가하지 않았다.

기본 parameter 수(새 부분 1,413,953 / heads 3,159,046), head dropout 0.1, fusion attention dropout 0, AdamW 기본값과 geometry/temporal sample 수를 CPU로 확인했다. HTML의 SGD learning-rate 계산(0, 0.1, 0.25, 0.6), 기존 stepper/계산기, 목차 anchor, desktop/mobile 배치와 신규 shell 예제 구문을 검증했다. 이 문서 검토가 기존 88개 코드 테스트나 실제 5080 검증을 새로 대체하지 않는다. 신규 본문 소스는 docs/guide/*.html이며 최종 결과는 여전히 외부 자산 없는 단일 HTML이다.
