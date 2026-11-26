# Claude 실행 지시서: FK 검증 · CAD-only 대조 · 결과 판정 · 가림 분석

작성: 2026-11-27. 대상 브랜치: `feat/omy-training-ready`.
기준 코드와 결과: `103c075` 및 [OMY_5080_RESULTS.md](OMY_5080_RESULTS.md).

## 그대로 맡길 작업

이 문서를 읽고 RTX 5080 환경에서 아래 네 작업을 구현·검증·실행한 뒤, 코드와 결과 보고서를 같은 브랜치에 올려 주세요.

1. 기존 데이터의 FK·좌표계·표면점 속도 정합을 검증한다.
2. 같은 temporal 학습 조건에서 visual / CAD-only / robot+CAD geometry를 3 seed로 비교한다.
3. 사전에 정한 지표로 CAD 정보와 로봇 정보의 기여를 구분해 결과를 판정한다.
4. 기존·신규 rollout의 가림 전/중/후 오차와 회복 과정을 그래프·overlay로 분석한다.

네 작업을 하나의 실행 계획으로 진행하되, GPU 학습은 순차 실행한다. 1번에서 오류가 확인되면 해당 입력에 의존하는 학습은 멈추고 수정·재검증한다. 기존 결과 보존, 입력 검사, 기존 결과의 읽기 전용 분석 등 독립적인 작업은 계속한다. 이 문서는 실행 지시서이며, 아래 신규 CLI와 결과 파일은 아직 구현되지 않았다. 기존 환경과 산출물을 먼저 확인하고 필요한 것만 추가한다.

범위 밖: 대체 backbone, on-policy 학습, 새 데이터 생성, AWS 사용, test 데이터로 설정 선택. 결과가 기대와 다르다는 이유로 학습 설정·지표·split을 임의 변경하지 않는다.

## 배경과 검증할 질문

- 45개 시퀀스: train 36, validation 9. 독립 test 없음.
- Temporal geometry: macro surface error 2.34mm, seed별 2.34/2.66/2.01mm, cylinder_C 마지막 오차 50mm 초과 0/3.
- Pilot geometry: 1.90/6.01/6.09mm, 같은 놓침 2/3. Pilot을 실패나 무효로 취급하지 않는다. 부분 가림에서는 pilot도 좋은 결과를 보였다.
- Kinematic-refine: macro 3.23mm. Temporal geometry는 평균 오차가 낮지만 diameter 10% 초과 프레임 비율은 4.1–5.6%로 baseline 3.3%보다 높았다.
- Temporal visual은 one-step val 약 3.6mm에도 rollout 평균 6.76mm. Temporal motion은 seed별 5.51/2.05/2.06mm로 불안정했다.
- 완전 가림 validation은 사실상 cylinder_C_04 하나. seed 3개는 독립 장면 3개가 아니다.

핵심 질문: 개선이 명시적인 CAD 표현만으로 설명되는가, 아니면 로봇 상태가 추가로 기여하는가? CAD 자체는 알려진 형상이며 현재 GT pose가 아니다. 결과가 CAD-only에 유리해도 오류나 부정한 입력이라고 결론 내리지 않는다.

## 실행 전 점검과 보존

- `git status`, 현재 commit, 설치 환경, 데이터·cache·checkpoint·초기 pose 경로를 확인한다. 진행 중 학습과 충돌하지 않는다.
- `docs/OMY_5080_RESULTS.md`에 기록된 로컬 경로를 찾아 재사용 가능한 산출물을 목록화한다. 경로 존재를 확인하지 않고 가정하지 않는다.
- 기존 `outputs/omy_training_5080_003`, `outputs/omy_comparison_5080_001`과 원본 데이터는 덮어쓰거나 삭제하지 않는다.
- 새 output root를 만들고 `plan.json`에 단계·명령·입출력·seed·실행 상태를 기록한다. 실패 후 재개는 완료한 항목의 provenance를 확인하고 미완료 항목만 수행한다.
- 반영된 회전 delta transpose, float64 crop diameter, float64 기구학 전파 수정이 있는지 확인한다. 수정 전 cache/checkpoint를 재사용하지 않는다.
- 학습과 평가의 소스 snapshot을 고정하고 commit/dirty diff hash를 기록한다. 같은 비교표의 rollout은 같은 소스 commit에서 생성한다. 기존 aggregate의 source_commit 일치 검사를 우회하지 않는다.
- 필요한 새 코드는 구현·테스트 후 commit하고 장시간 실험을 시작한다. 결과 문서 commit은 이후 별도로 가능하다.

## 작업 1 — FK·위치·속도 정합 감사

### 입력과 독립 기준

관측 joint_positions, joint inventory, robot base pose로 계산한 FK를 시뮬레이터가 저장한 링크 GT와 비교한다. 먼저 실제 export schema와 링크 기준 좌표계를 확인한다. GT는 이 감사의 기준으로만 사용하며 모델 입력 함수에 추가하지 않는다.

현재 관련 코드:
- `scripts/omy_kinematics.py`: 이름으로 관절값을 매핑하고 joint local frames와 회전을 합성.
- `src/robot_conditioned_pose/omy_sequence.py`: 같은 canonical 점, 실제 직전 프레임, 현재 카메라 좌표계, 1/30초 검사.
- `src/robot_conditioned_pose/geometry.py`: 후보 좌표계 변환, diameter 정규화.
- `tests/test_omy_training_integration.py`, `tests/test_robot_conditioned_pose.py`: 기존 합성 검사.

합성 테스트와 checksum 성공은 실제 FK의 기하 정확도를 증명하지 않는다. 2026-09의 robot projection 기록은 다른 capture에서 simulator link pose를 사용한 검증이므로 이번 measured-joint FK 검증으로 대체하지 않는다.

### 모든 45개 시퀀스에서 수행

1. frame ID/timestamp 정렬, 누락, dt, joint 이름·단위, base/camera transform, mesh/link offset, quaternion 순서를 확인.
2. **같은 링크 좌표계**의 FK와 GT pose에서 위치 오차(mm), 상대 회전각(deg)을 산출. 고정 mesh offset을 모르면 추정해서 억지로 맞추지 말고 export 정의에서 확인.
3. 동일 canonical 표면점을 FK와 GT로 각각 변환해 거리 오차(mm)를 계산. 같은 FK로 양쪽 기준을 만들지 않는다.
4. FK 점 차분과 GT 링크 pose로 만든 같은 점 차분을 비교. 두 시점 모두 동일한 현재 카메라 좌표계로 옮기고 실제 dt로 나눈다. 이 값은 구간 평균 속도이며 저장된 순간 속도와 동일하다고 가정하지 않는다.
5. 시뮬레이터 선속도/각속도가 있다면 정의된 기준점과 좌표계를 확인한 뒤 표면점 속도(v + ω×r)와 보조 비교한다. Jacobian×qdot만의 일치는 같은 기구학을 공유하므로 독립 GT 검증의 대체가 아니다.
6. 정지·회전·base 이동·camera 이동에 대한 합성 회귀 검사를 보완. 정지점의 가짜 속도, 단위 오류, 부호 반전, 한 프레임 지연에 대한 검출 여부를 확인.
7. raw 물리 단위와 모델에 넣는 정규화 값 모두 기록. 동일 point_features 함수로만 기대값을 계산하는 자기검증을 피한다.
8. 대표 프레임과 최악 프레임에 FK/GT 로봇 투영을 겹쳐 저장. 가려진 로봇까지 보이는 X-ray overlay와 가시성 고려 투영을 구분한다.

### 결과와 판단

`fk_audit.json`, 링크·프레임별 CSV, `fk_audit.md`, overlay PNG를 저장. 각 항목에 평균/중앙값/p95/최대, 최악 sequence/frame/link, NaN·누락 수를 포함한다.

**사전 조사 기준(공식 데이터 합격 규격 아님):** 위치·동일 표면점 p95 > 1mm 또는 최대 > 5mm, 회전 p95 > 0.5도 또는 최대 > 2도, 표면점 속도차 p95 > 0.02m/s 또는 최대 > 0.1m/s면 원인 조사 후 학습 진행 여부를 문서화한다. 시간 불일치·단위 오류·비유한 값은 hard fail. 임계 이하라도 체계적인 축/시간 편향을 확인한다. 임계 초과를 감추기 위해 기준을 완화하지 않는다. 관절 관측 노이즈가 의도된 데이터라면 그 크기와 예상 오차를 별도로 명시한다.

독립 링크 GT가 없으면 `UNVERIFIED`로 기록한다. 확인하지 못한 정확도를 PASS라고 쓰지 않는다. 이 경우 CAD-only/visual과 기존 결과 분석은 진행할 수 있지만, 로봇 상태 정확성을 전제로 한 결론은 보류하고 필요한 추가 export 필드를 보고한다. FK 오류가 확정되면 먼저 고치고 영향을 받은 cache 및 비교 실험을 새 output으로 재생성한다. 시각 cache를 무조건 유지하지 말고 변경 영향에 따라 재사용 여부를 판단한다.

## 작업 2 — Temporal CAD-only 3-seed 대조

### 고정할 실험 조건

- 동일 temporal cache의 visual tokens, hypothesis, GT target, sample 순서 목록을 공유. 합격한 cache manifest/hash를 보존.
- 20 epochs, batch 4, warmup 0, seed 42/43/44 각각 독립 초기화. 기존 best.pt에서 이어 학습하지 않는다.
- visual encoder frozen. Heads LR 1e-5; 신규 encoder/fusion LR 1e-4; 그 외 optimizer/clip/dropout/loss는 기존과 동일.
- 기존 one-step validation 최저 best.pt를 평가한다. 이번 주 실험에서 rollout 성능을 보고 임의로 checkpoint를 고르지 않는다.
- 3 modes × 3 seeds = 9회 학습. 같은 코드·cache·설정의 기존 실행임이 증명될 때만 학습 결과 재사용하고 기록한다.

### CAD-only의 정확한 정의와 구현

제안 모드 이름: `cad-only`. 아직 현재 CLI choices에 없으므로 먼저 구현한다.

- cache points의 is_robot 채널로 CAD 행을 선택한다(현재는 256점). 행 위치를 무조건 마지막 256개라고 가정하지 않는다.
- xyz/normal은 원본 CAD 점을 그대로 사용하고, robot flag/velocity/validity는 CAD의 원래 0을 유지한다.
- 가짜 로봇 점을 원점으로 만들거나 zero padding하지 않는다. 기존 geometry 모델에 추론 때만 로봇을 삭제하는 방식으로 대체하지 않는다.
- RobotEncoder(128/32 regions, radii, width), projection, position MLP, fusion, heads는 geometry와 같은 구조를 사용한다. 입력 점 수 256 vs 768에 따른 sampling/계산량 차이를 명시한다.
- mode 분기를 `forward_tokens`의 공통 경로에 구현해 cache 학습과 RGB-D rollout 양쪽에 동일 적용. trainer, CLI, checkpoint restore, evaluator, provenance 검사를 함께 연결한다. 기존 모드 동작을 바꾸지 않는다.
- 원본 cache를 수정하지 않는다. CAD-only와 geometry를 같은 points cache에서 결정적으로 구성한다. 각 batch의 CAD 개수가 달라지면 명시적으로 처리하거나 오류를 낸다.
- 원래의 Visual은 실제 신규 기하 분기를 bypass한다. Geometry는 속도/validity를 0으로 만든다. Motion은 이번 신규 학습 대상이 아니다.

테스트: CAD-only 출력이 로봇 행의 좌표·속도·순서 변화에 영향을 받지 않는지, 실제 CAD 행이 선택되는지, encoder/fusion gradient가 있는지, checkpoint mode가 복구되는지, 기존 geometry/visual의 출력 규약을 유지하는지 확인한다. 그런 다음 작은 GPU smoke를 거쳐 전체 학습한다.

점 수 대조가 필요하면 별도 `cad-only-768` 추가 실험을 설계한다. 중복 점 padding이 아니라 train/eval에서 동일한 결정적 CAD surface sampling을 사용하고 geometry 입력 규약과 provenance를 명시한다. 첫 9회 실행과 혼합하지 않으며, 256점 CAD-only 비교만으로 모든 confound가 제거됐다고 주장하지 않는다.

### 실행 명령 형태

다음은 **cad-only 지원 구현 후**의 실행 예시다. OMY_WORK는 확인한 기존 cache root, AUDIT_RUNS는 새 학습 output root로 설정한다.

```bash
for seed in 42 43 44; do
  for mode in visual cad-only geometry; do
    python scripts/train_robot_refiner.py \
      --train "$OMY_WORK/motion-train" \
      --val "$OMY_WORK/motion-validation" \
      --mode "$mode" --seed "$seed" \
      --epochs 20 --batch-size 4 --warmup-epochs 0 \
      --lr 1e-4 --head-lr 1e-5 \
      --output "$AUDIT_RUNS/temporal-${mode}-s${seed}" || exit 1
  done
done
```

현재 `run_omy_training.py --stage motion`은 visual/geometry/motion을 실행하며 cad-only는 포함하지 않는다. 따라서 그것을 이번 대조 실험 명령으로 사용하지 않는다.

## 작업 3 — 같은 조건 평가와 결과 판정

같은 9개 validation, 같은 첫 프레임 GT 초기 pose, 이후 GT reset 없음, 첫 프레임 집계 제외, refinement 2회, 평가 CAD 4096점/seed 2026, 같은 symmetry/diameter 규약으로 평가한다. 평가 전 실제 저장 설정을 검증한다.

신규 source snapshot에서 pretrained visual과 kinematic-refine도 다시 rollout하여 비교 provenance를 맞춘다. 동일 baseline을 seed별 표에 참조할 수 있지만 단 한 번의 baseline을 독립 3회 실험으로 세지 않는다. 예시는 기존 suite로 baseline을 각 seed에서 반복 실행하는 단순한 방식이다.

```bash
for seed in 42 43 44; do
  python scripts/run_omy_comparison.py \
    --dataset "$OMY_DATASET" --initial-poses "$OMY_INITIAL" \
    --initialization oracle-first-frame --iterations 2 \
    --methods visual kinematic-refine \
    --checkpoint "visual-ft=$AUDIT_RUNS/temporal-visual-s${seed}/best.pt" \
    --checkpoint "cad-only=$AUDIT_RUNS/temporal-cad-only-s${seed}/best.pt" \
    --checkpoint "geometry=$AUDIT_RUNS/temporal-geometry-s${seed}/best.pt" \
    --output "$AUDIT_EVAL/seed-${seed}" --execute || exit 1
 done
```

명령에 쓰는 경로는 먼저 확인하고, 모든 새 output은 읽기 전용 데이터셋 밖에 둔다.

다음 표들을 markdown/JSON으로 생성하고 한국어로 설명한다.

- 학습: 초기 pretrained reference, train/val 곡선, best epoch, 마지막 epoch, seed별 값. TensorBoard와 metrics.jsonl에 기록.
- 추적: seed별 9개 시퀀스, macro mean, median/p95/final surface error, diameter 10% 초과 프레임 비율, 처리 시간.
- seed별 paired difference: geometry − CAD-only, CAD-only − visual-ft. 음수이면 앞 모델의 오차가 작음.
- 쉬운 7개와 cylinder_A_04/cylinder_C_04를 따로 표시. 전체 macro를 선택적으로 어려운 시퀀스만의 결과로 바꾸지 않는다.
- 놓침(final > 50mm)과 failure_fraction_10pct_diameter는 별개 열로 표시.
- seed 평균과 범위를 표시하되 3 seed만으로 유의한 일반화나 독립 장면 수 증가를 주장하지 않는다.

판정 규칙:

| 관찰 | 허용하는 해석 |
|---|---|
| Robot+CAD가 CAD-only보다 여러 seed·시퀀스에서 개선 | 이 설정에서 로봇 입력의 추가 기여를 지지 |
| CAD-only와 Robot+CAD가 비슷 | 현 데이터에서 로봇 고유 기여가 분리되지 않음 |
| 평균은 비슷하고 가림 이탈만 감소 | 정확도보다 안정성에 기여할 가능성 |
| seed별 순위가 바뀜 | 효과가 불안정하거나 현재 데이터로 판별 불충분 |
| CAD-only도 악화 | 기하 정보가 자동으로 이득을 준다는 가정 기각; 설정·학습 결과 분석 |

정확한 로봇 기여의 강한 인과 주장에는 이후 robot-state mismatch 대조와 용량 대조 등이 더 필요하다. 이번 CAD-only 실험은 첫 분리 검사다. Pilot 결과도 이전 reference로 유지하되, 소스가 다른 결과는 새로운 matched 표와 구별해 표시한다.

## 작업 4 — 가림 전/중/후 분석

가능하면 9개 validation 전체에 대해 분석하고, cylinder_A_04와 cylinder_C_04의 상세 그림/overlay를 반드시 만든다. 기존 visibility_audit.json의 생성 방법과 분모를 검증한다. GT amodal silhouette과 visible mask의 픽셀 비율은 **분석에만** 사용한다. 가시 비율을 inference gate나 학습 입력으로 추가하지 않는다. 카메라 밖으로 잘린 경우나 분모 0은 따로 표시한다.

고정 visibility bin: ≥50%, 20–50%, 5–20%, <5%. <5%는 operational한 '거의 완전 가림' 기준이며 수학적으로 0%와 같지 않다. 시퀀스 이름 A/B/C를 frame별 contact label로 취급하지 않는다.

- x축 실제 timestamp; 상단 visibility, 중단 방법별 surface error(mm), 하단 가능하면 로봇/물체 움직임과 실제 이벤트 label.
- 방법별 mean/p95/max error를 visibility bin별, 그리고 가림 전/중/재등장 후로 분리. sample 수와 해당 시퀀스 수를 함께 표시.
- 심한 가림 event: <5%가 최소 3프레임 연속. 재등장 시점: 해당 event 후 ≥50%가 3프레임 연속되는 첫 구간 시작. event/interval 정의를 JSON에 기록.
- 회복 시간: 재등장 이후 surface error ≤0.1 diameter를 5프레임 연속 만족하는 첫 구간 시작까지 시간. 재등장 후 1초·2초 오차와 최종 오차도 표시. 영상이 먼저 끝나면 관측 불충분, 끝까지 회복 안 되면 미회복으로 구분한다. frame 0 초기화는 회복으로 세지 않는다.
- 이 회복 기준은 사전에 고정한 분석 지표이지 물체를 정확히 원위치로 찾았다는 보증은 아니다. threshold 아래에서도 남는 mm 오프셋을 함께 본다.
- 전체 timeline과 전환 구간 확대 그림을 함께 제공. 기존 pretrained/kinematic-refine, temporal visual/CAD-only/geometry를 같은 축에 비교. 기존 pilot/motion은 별도 reference 그림으로 가능.
- seed 42를 공통 시각화 seed로 미리 정하고 모든 seed의 수치·곡선을 제공한다. 추가 최악 사례를 보여줄 때 선택 기준을 명시한다. 잘된 seed만 고르지 않는다.
- overlay는 원래 RGB, 추정/GT 물체, FK 로봇을 구별. 동일 frame을 같은 색 규약으로 비교하며 별도 전시용 GT 보정을 하지 않는다.

## 저장할 산출물과 GitHub 보고

새 output 아래에 최소 다음을 남긴다.

```text
plan.json / environment.txt / provenance.json
fk_audit/{summary.json, per_frame.csv, report.md, overlays/}
training/temporal-{mode}-s{seed}/{metrics.jsonl,best.pt,last.pt,tensorboard/}
evaluation/seed-{seed}/{comparison.md,comparison.json,...}
analysis/{paired_differences.csv, visibility_bins.csv, recovery_events.csv, figures/, videos/}
```

저장소에는 다음을 올린다.

- 추가·수정한 코드, 의미 있는 regression tests, 정확한 재현 명령.
- `docs/OMY_CAD_ABLATION_RESULTS.md`: 결론 먼저, 수치·조건·seed별 결과·한계·미완료 항목.
- `docs/OMY_FK_AUDIT_RESULTS.md`: 검증 범위, 독립 기준 유무, 오차 표, pass/fail/unverified와 조치.
- 작고 검토 가능한 요약 CSV/JSON 및 그래프 PNG. 그래프는 실제 로그에서 생성하고 예시 수치를 섞지 않는다.
- checkpoint, 원본 데이터, 대형 event/영상은 기존 정책대로 로컬 보존하고 경로/hash를 기록. 임의로 대용량을 Git에 추가하지 않는다.
- HTML은 생성기와 docs/guide 소스 체계를 유지하며 새 결과의 짧은 요약과 접이식 설명을 추가한다. 기존 섹션 번호를 바꾸지 않는다.

문서 검토 시 이전 HTML의 회전 decode 설명과 'GPU 검증 전' 표현도 최신 결과 범위에 맞춰 정정한다. 현재 ΔR은 raw axis-angle 변환 행렬의 transpose를 사용하고, R_new=ΔR R_current이다. 실제 수행한 검사만 완료로 표시한다.

## 종료 기준

- 네 작업 각각에 완료/차단/부분 완료 상태와 근거가 있다.
- FK 정확도를 확인하지 못하면 이유와 필요한 파일을 명시한다. CAD-only는 독립 학습과 rollout 양쪽에서 같은 정의다.
- 9개 신규 학습 또는 정당한 재사용 증거, matched rollout, paired 비교, 가림 그래프가 있다.
- 결과가 개선되지 않아도 그대로 기록한다. validation 재사용·소수 시퀀스·oracle 초기화 한계를 명시한다.
- 테스트와 필요한 GPU smoke를 수행하고, 최종 branch/commit과 보고서 링크를 반환한다.
- 다음 단계는 결과를 근거로 제안만 한다. on-policy 학습·backbone 변경·데이터 생성은 이번 실행에 끼워 넣지 않는다.
