# OMY 통합 검증 기록

2026년 11월 24일 로컬 CPU 검증: `58 passed, 1 skipped`, 15.55초. 격리된 임시 Python 3.9 환경, torch 2.8.0, numpy 2.0.2, scipy 1.13.1을 사용했다. 이는 GPU 환경 dependency lock이 아니다.

기존 테스트는 surrogate encoder를 통한 gradient, 작은 학습, checkpoint 및 resume를 포함한다. 추가 테스트는 실제 FK 코드에 합성 관절 inventory/mesh를 제공하여 다음을 확인한다.

- GT 파일이 없어도 OMY adapter 구성, RGB-D 읽기, 768×11 point feature 생성 가능.
- 현재/이전 동일 표면점에서 비영 속도 생성, frame 0에서도 preroll 관측 사용.
- 반복 reader 생성 시 canonical/CAD 샘플 일치.
- GT frame 순서 불일치 거부.
- train/validation physical-parent overlap 거부.
- 잘못된 checksum 및 dataset 밖 경로 거부.

CLI smoke/motion 실행 계획 출력과 Python 구문 검사, git diff whitespace 검사도 통과했다. 실제 OMY payload checksum, FoundationPose CUDA parity/rendering, 실제 데이터 tiny overfit, 5080/L40S 호환성 및 throughput은 GPU 머신의 다음 검증 단계다. 자동 실행기는 이를 우회하지 않고 실패 시 중단한다.

소스 ZIP은 CPU 테스트된 작업본이다. GitHub push, AWS 생성/연결, 실제 데이터 학습은 수행하지 않았다. 기존 OMY_FIRST_TRAINING_PLAN.md는 통합 전 계획 기록이며 현재 실행법은 OMY_TRAINING_QUICKSTART.md를 따른다.
