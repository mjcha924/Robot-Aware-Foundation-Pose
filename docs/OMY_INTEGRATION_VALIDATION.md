# OMY 통합 검증 기록

2026년 11월 24일 로컬 CPU 검증: `79 passed, 1 skipped`. 격리된 임시 Python 3.9 환경, torch 2.8.0, numpy 2.0.2, scipy 1.13.1을 사용했다. 이는 GPU 환경 dependency lock이 아니다.

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

HTML은 20개 절로 확장했으며 desktop/mobile 가로 넘침, 학습 단계 버튼, 계산기, JavaScript 오류와 신규 실험 명령 포함 여부를 확인했다. `python scripts/build_omy_training_guide.py`로 문서 소스에서 재생성할 수 있다.
