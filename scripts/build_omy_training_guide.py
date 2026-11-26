#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import html,re
root=Path(__file__).resolve().parents[1]
sections=[]
def sec(id,title,body):sections.append((id,title,body))
def table(headers,rows):return '<div class="table"><table><thead><tr>'+''.join('<th>'+v+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def pre(s):return '<pre><code>'+html.escape(s.strip())+'</code></pre>'
sec('start','01 · 우리가 학습하려는 것','''<p class="lead">FoundationPose가 이미 이해하는 시각 정보에 <strong>로봇의 형상과 움직임</strong>을 보태, 물체가 가려지는 조작 과정에서 물체의 6D pose를 더 잘 추적할 수 있는지 시험한다.</p><p>6D pose는 위치 3자유도와 회전 3자유도다. 로봇의 행동을 생성하는 정책을 학습하는 프로젝트가 아니다. 현재 RGB-D와 pose hypothesis를 보고 물체 자세를 수정하는 <strong>refiner</strong>를 학습한다. 물체 CAD를 아는 model-based 조건이다.</p><div class="callout">2026-11-26~27에 RTX 5080에서 smoke, tiny, pilot·motion 3-seed, FK 감사와 CAD-only 대조를 실제로 실행했다. 실행 중 발견한 회전 부호·dtype·float32 누적 오차 문제는 수정했다. 측정 결과와 그 한계는 <a href="#validation-results">27절</a>과 docs/OMY_5080_RESULTS.md, docs/OMY_FK_AUDIT_RESULTS.md, docs/OMY_CAD_ABLATION_RESULTS.md에 있다. 모든 추적 수치는 첫 프레임 GT 초기화(oracle-first-frame) 조건이고, 9개 validation 시퀀스를 선택과 평가에 함께 썼다. 독립 test와 실사용 초기화 결과는 아직 없다.</div><p><strong>구현·실험 안내 빠르게 찾기:</strong> <a href="#review-fixes">17 · 리뷰 수정</a> → <a href="#motion-baseline">18 · 기구학 prior</a> → <a href="#experiment-order">19 · 실험 명령</a> → <a href="#research-next">20 · 결과 해석</a>. 기존 geometry 규약의 cache는 새로 만들어야 한다. 추적 결과 영상은 <a href="#tracking-visualization">21절</a>에서 확인한다.</p><p>처음 학습한다면 <a href="#study-path">26절 공부 순서</a>를 먼저 보고, <a href="#pose-math">22절 좌표계</a> → <a href="#learning-math">23절 학습 원리</a> → <a href="#architecture-detail">24절 구조</a> → <a href="#first-run">25절 첫 실행 관문</a>을 따라간다. 실제 명령은 10·19·21절에 있다. 페이지의 수치 예시는 실제 학습 결과가 아니라 계산 예시로 표시했다.</p>''')
sec('terms','02 · 먼저 익힐 학습 용어',table(['용어','우리 코드에서의 의미'],[
('Sample','한 프레임의 관측 + 시작 pose + robot points + 정답 pose 묶음. 한 프레임에 다른 시작 pose를 만들면 다른 sample이 될 수 있다.'),
('Parameter / weight','학습으로 바뀌는 숫자. Point encoder의 Linear 가중치, attention 가중치 등이 해당한다. 관절값 q는 입력 데이터이지 학습 파라미터가 아니다.'),
('Batch','한 번의 업데이트에 사용하는 sample 묶음. batch 4면 보통 4개 sample의 평균 오차로 업데이트한다.'),
('Step / iteration','학습에서는 대개 optimizer 업데이트 한 번. 추론 refinement iteration은 pose 수정 반복 횟수로, 학습 step과 다르다.'),
('Epoch','train sample을 한 차례 모두 사용한 단위. 20 epochs는 같은 데이터에서 20번 학습한다는 뜻이다.'),
('Loss','모델이 얼마나 틀렸는지 나타내는 미분 가능한 숫자. 여기서는 물체 CAD 표면점 위치의 평균 오차다.'),
('Gradient / backward','각 weight를 어느 방향으로 바꾸면 loss가 줄어드는지 연쇄 미분으로 계산하는 과정.'),
('Learning rate','업데이트 크기를 조절하는 값. 너무 크면 발산할 수 있고 너무 작으면 변화가 느릴 수 있다.'),
('Optimizer','gradient로 실제 weight를 업데이트하는 규칙. 이 코드에서는 AdamW를 사용한다.'),
('Frozen','weight를 업데이트하지 않는 상태. 해당 연산의 입력으로 gradient를 전달하는 것과는 별개다.'),
('Checkpoint','학습 중 weight와 optimizer 상태 등을 저장한 파일. pretrained weights는 출발점, 우리의 best.pt는 학습 결과다.'),
('Train / validation / test','train은 업데이트용, validation은 선택·조정용, test는 최종 독립 평가용. 현재 9개는 validation이며 독립 test가 아니다.')]))
sec('dataset','03 · 데이터는 무엇을 가르치는가',table(['유형','관측 상황','배워야 할 관계'],[
('A · 비접촉 가림','물체는 놓여 있고 로봇이 앞을 지나간다.','로봇이 움직였다고 물체까지 움직였다고 추정하면 안 된다.'),
('B · Grasp / carry','시뮬레이터의 물리적 grasp 후 lift, hold, 이동과 회전.','로봇 motion이 object motion에 유용할 수 있다.'),
('C · Place / release','잡힌 물체를 놓고 로봇이 물러난다.','release 이후에는 로봇 motion을 계속 따라가면 안 된다.')])+'''<p>현재 데이터는 Isaac Sim에서 수집한 시뮬레이션이다. Measured joint state는 명령 관절값 대신 시뮬레이터가 기록한 관측값을 쓴다는 뜻이며 실물 로봇 센서 데이터라는 뜻은 아니다. 물체는 gelatin box, large marker, banana 세 개다. 총 45개 시퀀스·11,999프레임(30 Hz). Train 36개·9,617프레임, validation 9개·2,382프레임이다. 5프레임마다 하나씩 고르면 최대 train 1,926 / validation 478 sample이다. 11,999프레임은 11,999개의 독립 장면을 뜻하지 않는다.</p><p>Physical parent는 원래 같은 물리 rollout에서 나온 clip의 묶음이다. 같은 parent의 B/C가 train과 validation에 나뉘면 거의 같은 장면을 미리 본 셈이 된다. 원래 manifest split을 유지하고 parent 중복을 검사한다.</p>'''+pre('''dataset/
  box_B_00/
    manifest.json                 # 경로·단위·camera·mesh·split 정보
    rgb/  depth/                  # 현재 센서 관측
    robot_observations.jsonl      # 관절 관측과 calibration
    previous_robot_state.json     # clip 시작 전 robot state
    robot/                        # link mesh와 joint inventory
    mesh/                         # 물체 CAD 및 texture
    frames.jsonl                  # GT를 포함하는 privileged label
    validation/                   # contact·phase·검증 기록
  ...''')+'''<div class="callout">Git에는 코드와 목록이 있다. 약 7.54GB의 데이터 payload와 pretrained weights는 각각 별도 준비한다. 일반 추적에서 contact·phase·현재 object GT를 입력으로 쓰지 않는다. GT는 학습·평가에 쓰며, 명시적인 oracle-first-frame 진단에서는 모든 방법의 첫 pose에 한 번 제공한다.</div>''')
sec('architecture','04 · 정해둔 아키텍처', '''<div class="arch"><div class="lane"><div class="node">현재 RGB-D<br>+ hypothesis에서 렌더링한 CAD</div><span>↓</span><div class="node frozen">FoundationPose encoder<br>encodeA → encodeAB → positional embedding<br><b>Frozen</b></div><span>↓</span><div class="node">Visual tokens · [B, L, 512]<br>attention의 Query</div></div><div class="lane"><div class="node">현재·이전 measured joint state<br>+ 로봇 mesh + 물체 CAD</div><span>↓</span><div class="node">FK · 동일 표면점의 위치/법선/속도<br>hypothesis 좌표계와 크기로 정규화</div><span>↓</span><div class="node trained">Robot + CAD local encoder<br>768 points → 128 regions → 32 tokens<br>[B, 32, 512] · Key / Value (robot + CAD)</div></div><div class="merge node trained">Residual cross-attention<br>Fused = Visual + α × Attention(Visual, Robot, Robot)</div><div class="merge node">Pretrained translation / rotation heads<br>각 token의 출력 평균 → Δtranslation, Δrotation → 새 pose</div></div><p>B는 batch size, L은 visual token 수다. L은 crop 크기와 encoder 출력에 따라 정해지므로 고정 숫자로 가정하지 않는다. 기본 RobotEncoder는 로봇점과 CAD점을 함께 모아 32개 local token을 만든다. Robot-only token이나 link별 token을 의미하지 않는다. 예전 설계 토론의 64/128 token 후보와 현재 구현을 구분하자.</p><p><strong>왜 여러 local token인가?</strong> 각 시각 위치가 다른 로봇 영역을 참조할 수 있게 하려는 것이다. 로봇 전체를 하나의 벡터로 줄이면 일반적인 softmax cross-attention의 Key가 하나여서 query에 따른 선택이 사라진다. 다만 cross-attention을 넣었다는 사실만으로 성능이 좋아지는 것은 아니다.</p><p><strong>왜 residual인가?</strong> 원래 시각 특징을 유지하면서 필요한 보정만 더한다. α는 0.01에서 시작하는 학습 가능한 scale이다. 학습을 거치며 크기와 부호가 바뀔 수 있고, 현재 코드에 범위 제한은 없다. α=0은 유한한 입력에서 residual 출력을 없애지만 branch 계산은 수행한다. bypass/visual 모드는 branch 자체를 건너뛴다. α는 contact 확률이나 frame별 trust gate가 아니다.</p>'''+table(['부분','Tiny 진단','Geometry/motion 비교 학습'],[('Visual encoder','고정','고정'),('Robot encoder + fusion','함께 학습','함께 학습'),('Pose heads','고정','1e-5로 학습')]))
sections[-1] = (*sections[-1][:2], sections[-1][2] + (root/'docs/guide/04_architecture_walkthrough.html').read_text(encoding='utf-8'))
sec('features','05 · Robot state가 신경망 입력이 되는 과정','''<p>관절각 q를 그 자체로 단순 연결하지 않는다. <strong>q → FK → 로봇 표면점</strong>으로 바꿔 영상과 비교할 수 있는 기하 표현을 만든다. FK는 joint inventory에 정의된 관절축·부모/자식 관계와 관측 관절각으로 link pose를 계산한다.</p><ol><li>각 link mesh에서 canonical point를 고정 샘플링한다. 전체 로봇 512점이다.</li><li>같은 표면점을 현재와 이전 관절 상태로 각각 변환한다. 매 프레임 다른 점을 뽑으면 속도 계산에 샘플링 노이즈가 섞인다.</li><li>두 시점의 점을 <strong>동일한 현재 카메라 좌표계</strong>로 표현한다.</li><li>(현재점 − 이전점) / Δt로 속도를 계산한다. 새 reader의 motion_camera_m 자체는 변위이므로 바로 속도로 사용하면 안 된다.</li><li>시작 pose의 역변환을 적용하고 물체 diameter로 정규화한다. 법선은 회전만 적용한다.</li><li>물체 CAD 256점을 더해 총 768개의 11차원 점을 만든다.</li></ol>'''+table(['채널','크기','의미'],[('xyz / diameter','3','hypothesis 기준 위치, 무차원'),('normal','3','표면 방향. 크기 정규화하지 않음'),('velocity / diameter','3','초당 움직임, 단위 1/s'),('is_robot','1','로봇점 1, CAD점 0'),('velocity_valid','1','robot 관측 속도 유효 여부, 물체 CAD 속도는 미지이므로 0')])+'''<p>Geometry 모드는 속도와 validity 채널을 0으로 만든다. Motion 모드는 이를 유지한다. 물체 CAD는 이미 알고 있는 형상이고, GT 현재 pose로 배치된 점을 몰래 넣는 것이 아니다.</p><details><summary>좌표계에서 자주 생기는 오류</summary><p>T_A_B는 B 좌표를 A로 바꾼다. depth PNG는 mm지만 모델은 m를 사용한다. object root, raw mesh, centered mesh frame을 혼동하지 않는다. 현재 adapter는 관측과 FK를 재사용하고 모델의 raw mesh hypothesis로 직접 point feature를 만든다. 공개 reader의 object-root pose API와 혼동하지 않는다. frame 0의 속도도 실제 previous_robot_state로 계산한다.</p></details>''')
sec('hypothesis','06 · 정답과 시작 pose는 어떻게 만드는가', '''<p>학습 샘플은 “물체를 처음 발견하는 문제”보다 <strong>주어진 pose를 고치는 문제</strong>다. Registration은 별도의 초기화 단계이고, 이 코드의 학습 대상은 refinement다.</p>'''+table(['모드','시작 pose','해석'],[('perturbed','현재 GT pose에 translation/rotation 노이즈','첫 geometry 학습과 구현 검증'),('previous','직전 GT pose를 현재 camera로 옮긴 뒤 노이즈','motion과 다음 pose update 관계를 배우는 temporal supervision'),('평가 rollout','직전 모델 prediction','오차가 누적되는 실제 tracking 조건')])+'''<p>기본 perturbation은 translation 각 축 표준편차 0.01m, rotation axis-angle 각 성분 표준편차 10°다. “언제나 정확히 10mm·10° 틀린다”는 뜻이 아니다. 표준편차가 있는 확률 분포에서 뽑는다.</p><p>Previous 모드는 선택 프레임이 5프레임 간격이어도 실제 직전 프레임 i−1의 pose를 사용한다. frame 0에는 이전 object GT가 없으므로 제외한다. 이를 문서에서 teacher-forced hypothesis라고 부른다. 이전 GT를 쓰지만 recurrent sequence 모델을 학습하는 것은 아니며, 현재는 각 sample을 독립적인 한 번의 refinement로 학습한다. 모델 자신의 이전 prediction 분포를 쓰는 on-policy 학습도 아니다.</p><div class="callout">GT를 학습 target이나 학습용 hypothesis 생성에 쓰는 것은 supervised learning의 일부다. 추론에서 매 프레임 GT를 넣거나, validation 정답으로 tracking을 계속 초기화하면 다른 평가가 된다.</div>''')
sec('cache','07 · 왜 먼저 cache를 만드는가','''<p>Rendering과 visual encoder는 GPU 비용이 들지만, 이번에는 visual encoder를 고정한다. 같은 sample을 20번 학습하면서 같은 렌더링을 20번 할 필요가 없으므로 visual token을 한 번 저장한다.</p>'''+pre('''prepare_robot_refiner.py
  sequence 읽기 → hypothesis 만들기
  → RenderBridge.pair(): 실제 RGB-D와 렌더 crop 구성
  → model.encode_visual(): frozen feature 추출
  → point features + target + CAD와 함께 sample .pt 저장
  → heads.pt, manifest.json 저장

train_robot_refiner.py
  cache 읽기 → robot encoder → fusion → pose heads
  → loss → backward → optimizer.step()''')+'''<p>Cache에는 visual, points, hypothesis, target, CAD, diameter, symmetries가 들어 있다. Manifest는 weight hash, upstream commit, config, sequence hash와 parent group을 기록한다. 서로 다른 원본 weights나 config의 cache를 섞으면 거부한다.</p><p><strong>Hypothesis를 바꾸면 렌더 crop과 visual token도 바뀐다.</strong> 그래서 temporal cache는 별도로 만든다. 이 방식은 fixed augmentation이다. 더 많은 epoch를 돌려도 새로운 random perturbation이 자동으로 생성되지는 않는다.</p>''')
sec('loop','08 · 학습 step 안에서는 무슨 일이 일어나는가','''<div class="stepper"><div id="step-label" aria-live="polite"></div><p id="step-detail"></p><button id="prev" type="button">← 이전</button> <button id="next" type="button">다음 →</button></div>'''+pre('''for batch in train_loader:
    optimizer.zero_grad(set_to_none=True)
    output = model.forward_tokens(batch['visual'], batch['points'])
    predicted_pose = decode_pose(output, batch['hypothesis'], ...)
    loss = pose_loss(predicted_pose, batch['target'], batch['cad'], ...)
    loss.backward()
    clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()''')+'''<p>이 코드는 개념을 보여주기 위해 인자를 줄인 것이다. 실제 구현은 trainer.py의 batch_loss()와 run()에 있다. AdamW는 gradient의 누적 통계도 가지고 있어서 resume에 optimizer state가 필요하다. Gradient clipping은 전체 gradient norm이 1을 넘으면 크기를 제한한다. 현재 warmup은 heads freeze 기간이며 learning-rate ramp가 아니다.</p><p>각 epoch가 끝나면 <code>model.eval()</code>과 <code>no_grad()</code>로 validation을 수행한다. Validation에서는 weight를 업데이트하지 않는다. 이 결과가 가장 낮으면 best.pt를 갱신하고, 마지막 상태는 last.pt에 저장한다.</p><details><summary>Frozen heads인데 어떻게 encoder가 학습되는가?</summary><p>heads weight의 requires_grad=False는 weight를 바꾸지 않겠다는 뜻이다. heads가 입력 특징에 수행하는 연산은 여전히 미분 가능하다. loss의 gradient는 heads를 통과해 fusion과 robot encoder로 전달된다. 따라서 heads 전체를 no_grad로 감싸면 이 학습 경로를 끊을 수 있다. 현재 visual encoder와 그 앞단은 학습 대상이 아니므로 cache 생성에서 no_grad를 사용한다. 반면 Tiny heads는 weight가 고정돼도 train 모드의 dropout은 켜져 있다. 23절에서 freeze/no_grad/eval을 구분한다.</p></details>''')
sec('loss','09 · Loss와 hyperparameter를 읽는 법','''<p>예측 pose로 변환한 CAD점과 GT pose로 변환한 같은 CAD점 사이의 거리를 평균한다.</p><div class="formula">L = meanᵢ ‖ T̂ pᵢ − Tᴳᵀ pᵢ ‖₂</div><p>정확한 대칭 변환이 제공되면 허용된 변환 중 최소 오차를 택한다. 없으면 identity만 사용한다. 원통처럼 보인다는 이유로 texture·형상의 대칭을 임의로 선언하지 않는다. 이 loss는 무조건 최근접점을 찾는 ADD-S와 같은 정의가 아니다.</p><p>예를 들어 surface error 0.004는 평균 4mm다. 이것은 translation error 4mm와 같지 않다. 회전이 틀려도 표면점 위치가 어긋나기 때문이다.</p>'''+table(['설정','기본값','바꾸면 무엇이 달라지는가'],[('batch-size','4','VRAM과 update당 sample 수. OOM이면 2/1로 낮추되 비교 실험 조건을 기록한다.'),('epochs','20','학습 반복 횟수. 많다고 항상 validation이 좋아지지 않는다.'),('lr','1e-4','새 encoder/fusion 업데이트 크기.'),('head-lr','1e-5','pretrained heads를 더 작게 조정한다.'),('warmup-epochs','Tiny 20, pilot/motion 0','해당 epoch 동안 heads 고정. visual-only에서 양수는 학습 대상이 없어 오류로 막는다.'),('stride','5','cache에 선택할 프레임 간격. 로봇 속도 계산 Δt와 다르다.'),('weight_decay','0.01 (PyTorch 2.8 기본값)','AdamW가 적용하는 decay. CLI에 별도 옵션은 없다.'),('dropout','heads 0.1 / fusion attention 0','train과 eval의 결과 차이를 이해할 때 확인. Tiny heads freeze에서도 train dropout은 활성.'),('seed','학습 42','초기화·shuffle 재현에 도움. 다른 GPU 간 완전 동일 결과를 보장하지 않는다.')])+'''<h3>계산량 직접 계산하기</h3><p>고정 geometry cache의 train 1,926 / validation 478개를 기준으로 한 산술 계산이다. 시간·성능 예측은 아니다.</p><div class="controls"><label>Batch <input id="batch" type="number" min="1" max="128" value="4"></label><label>Epochs <input id="epochs" type="number" min="1" max="1000" value="20"></label></div><output id="calc" aria-live="polite"></output>''')
# Render command guide from markdown; standalone and entirely inline.
md=(root/'docs/RUN_ON_5080.md').read_text()
def inline(s):
 s=html.escape(s);s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s);s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
 s=re.sub(r'\[([^]]+)\]\((https://[^)]+)\)',r'<a href="\2">\1</a>',s)
 return s
parts=md.split('```');rendered=[]
for i,part in enumerate(parts):
 if i%2:rendered.append(pre(part.split('\n',1)[1] if '\n' in part else part))
 else:
  for block in part.strip().split('\n\n'):
   if not block.strip():continue
   if block.startswith('# '):continue
   if block.startswith('## '):rendered.append('<h3>'+inline(block[3:])+'</h3>')
   else:rendered.append('<p>'+inline(block).replace('\n',' ')+'</p>')
sec('run','10 · 5080에서 순서대로 실행하기',''.join(rendered))
sec('code','11 · 코드 읽기 지도',table(['파일','먼저 볼 함수 / 역할'],[
('scripts/run_omy_training.py','main(): 단계별 명령을 구성. --execute 없이는 출력만 한다. verify_checksums(): 공식 payload 파일 검사.'),
('scripts/prepare_robot_refiner.py','main(): sequence loop, hypothesis 생성, rendering, visual feature 저장.'),
('src/robot_conditioned_pose/omy_sequence.py','OmySequence.points(): 측정 관절 기반 point feature. target(): 필요할 때만 GT 읽기.'),
('scripts/read_omy_tracking_sample.py','데이터 브랜치의 공개 reader 원본. 학습 adapter는 중복 I/O를 없앤 자체 관측/FK 경로를 사용한다.'),
('scripts/omy_kinematics.py','forward_kinematics(): joint inventory와 q에서 link transform 계산.'),
('scripts/omy_robot_surface.py','canonical_surface_points(), robot_surface_pair(): 표면점 대응 유지.'),
('src/robot_conditioned_pose/model.py','RobotEncoder, SetAbstraction, forward_tokens(): 핵심 신경망.'),
('src/robot_conditioned_pose/upstream.py','RenderBridge.pair()/refine(): 원본 FoundationPose 전처리·렌더링 연결.'),
('src/robot_conditioned_pose/geometry.py','point_features(), decode_pose(), pose_loss(): 단위·좌표·출력 해석.'),
('src/robot_conditioned_pose/data.py','FeatureDataset, collate, check_splits(): cache loading 및 split 검사.'),
('src/robot_conditioned_pose/trainer.py','run(): optimizer, epoch, validation, checkpoint. CachedHeads: 원본 heads 구조 복원.'),
('scripts/evaluate_robot_tracker.py','prediction을 다음 프레임에 전달하는 rollout. GT는 예측 이후 평가에 사용.'),
('src/robot_conditioned_pose/contracts.py','semantic_config(), mesh_diameter(): 이동 가능한 가중치 동일성 및 정확한 diameter.'),
('src/robot_conditioned_pose/motion_prior.py','propagate_pose(): 카메라 보상과 rigid-grasp SE(3) propagation.'),
('scripts/run_omy_comparison.py','validation 9개를 같은 초기화로 비교하고 macro 결과표를 생성.'),
('scripts/visualize_robot_tracker.py','저장된 추정 pose·GT·측정 FK를 RGB에 겹쳐 CPU MP4/PNG로 저장. 21절 실행 안내.'),
('scripts/prepare_omy_initial_poses.py','명시적인 첫 프레임 GT 초기화 진단 준비. 일반 추론과 분리.'),
('tests/test_motion_baselines.py','기구학, 경로 이동, 재현성, 동일 초기화, CPU rollout/집계 회귀 검사.'),
('tests/test_omy_training_integration.py','GT 없는 입력 구성·속도·parent leakage·checksum 실패 검증.')])+'''<p>추천 읽기 순서는 <strong>run_omy_training → prepare → omy_sequence → model → geometry → trainer → evaluate</strong>다. import 전체를 처음부터 이해하려고 하기보다 한 sample의 shape가 어떻게 바뀌는지 따라가자.</p>''')
sec('results','12 · 로그와 결과를 해석하기',pre('''# 아래는 형식을 보여주는 가상 예시다. 실제 측정 결과가 아니다.
{"epoch": 0, "train_surface_error_m": 0.012,
 "val_surface_error_m": 0.015, "seconds": 80.0,
 "peak_cuda_bytes": 2100000000}''')+table(['관찰','가능한 해석','다음 행동'],[
('Tiny train loss가 줄어듦','최소한 일부 sample을 맞출 수 있는 학습 경로가 있다.','held-out validation과 rollout으로 진행.'),
('Tiny부터 줄지 않음','좌표, loss, gradient, 입력/정답 대응, 학습률 문제 가능.','전체 학습 전 pipeline 점검. architecture 실패로 바로 결론내리지 않기.'),
('Train만 좋아지고 validation 악화','과적합, 데이터 다양성 부족, 조건 차이 가능.','best checkpoint 비교, split과 augmentation 확인.'),
('원본보다 좋지만 visual-only와 같음','추가 학습 효과일 수 있다.','robot state의 이득이라고 주장하지 않기.'),
('Geometry 좋고 motion 차이 없음','motion 정보의 가치/학습 구성/장면 난이도 문제 가능.','B와 release 구간을 나눠 보고 state 교란 실험.'),
('한 프레임 평가는 좋지만 rollout 나쁨','GT hypothesis와 실제 prediction의 분포 차이, 누적 drift.','train prediction 기반 hypothesis 확장 검토.')])+'''<p>Train loss는 epoch 동안 weight가 계속 바뀌며 계산한 평균이고, validation은 epoch 끝 모델로 계산한다. train/eval 모드의 dropout 차이도 있으므로 두 숫자의 대소만으로 오류라고 판단하지 않는다.</p><p>metrics.jsonl의 peak_cuda_bytes는 PyTorch의 peak allocated memory이지 nvidia-smi 전체 점유량이 아니다. 시간은 epoch의 학습+validation 중심이며 cache 생성·환경 설치 시간은 별도다.</p>''')
sec('evaluation','13 · 학습 완료 후 무엇을 증명해야 하는가','''<p>먼저 pretrained visual control, same-data visual-only, geometry, geometry+motion을 같은 초기화·mask·split 조건에서 비교한다. Geometry와 motion 비교는 같은 temporal cache에서 해야 hypothesis 차이를 robot motion 효과로 혼동하지 않는다.</p><ul><li>A/B/C, 가시성 구간별 error와 실패율을 따로 본다.</li><li>정확한 state와 시간 지연/교란 state를 비교해 robot 정보를 실제로 쓰는지 본다.</li><li>새 branch에는 CAD점도 추가되므로 robot 정보만의 효과를 더 분리하려면 object-CAD-only 대조군을 추가한다.</li><li>안정적인 grasp의 gripper-motion propagation과 그 prior를 사용하는 pretrained refinement를 18~19절에서 실제 비교한다.</li><li>C의 부분 가림 초기화는 별도 병목이다. 동일 GT 초기화 진단과 실제 initialization 평가를 구분한다.</li></ul><p>현재 evaluate_robot_tracker는 동일 RenderBridge의 sequence runner다. upstream track_one의 모든 전처리와 완전 동일하다는 보장은 아니다. 자체 초기화·실패 감지·재초기화 모듈도 아직 없다.</p><div class="callout">우리의 contribution 후보는 “encoder 두 개를 합쳤다”가 아니라, 조작 중 robot geometry·motion이 visual tracking을 보완하는 조건을 분리해 보이는 것이다. 기존 V-HOP 등 관련 연구가 있으므로 구조 자체의 최초성이나 효과를 아직 주장하지 않는다.</div>''')
sec('trouble','14 · 막혔을 때 읽을 부분',table(['증상','확인할 것'],[
('torch.cuda.is_available()가 False','활성 Python, driver, 컨테이너 GPU 접근, torch CUDA build. CPU 환경에서 실제 rendering은 불가.'),
('no kernel image / native extension 오류','5080 Blackwell 지원 build인지, mycpp/nvdiffrast 등 확장을 현재 torch/CUDA에 맞춰 빌드했는지.'),
('weights 경로 없음 / config 오류','submodule 내부 upstream weights 폴더 구조. 캐시만 있으면 rendering까지 가능한 것은 아니다.'),
('새 PyTorch의 torch.load 오류','원본 loader와 설치 PyTorch의 serialization 기본값 차이 가능. 출처 확인 없이 임의 checkpoint에 안전 옵션을 해제하지 말고 실제 traceback으로 진단.'),
('Checksum mismatch / missing file','공식 최종 dataset인지, 디렉터리명이 dataset인지, 전송이 완전한지. 교체 전 C clip을 섞지 않기.'),
('Output already exists','기존 결과 보호다. 새 work/output 경로 또는 완료되지 않은 개별 단계만 사용.'),
('CUDA out of memory','다른 GPU 프로세스와 batch 확인. 개별 train 명령에서 batch 2/1로 시작하고 비교 조건도 동일하게 유지.'),
('NaN / non-finite loss','depth 단위, transform, diameter, sample 대응, learning rate 확인. 오류를 무시하고 더 돌리지 않기.'),
('Resume provenance mismatch','같은 cache·mode·weights/config인지 확인. cache를 바꾼 재개는 지원하지 않음.')])+'''<p>처음은 단일 GPU FP32로 진행한다. AMP/BF16, 다중 GPU, 추가 custom CUDA 최적화는 correctness가 확인된 뒤 검토한다. 특히 renderer와 pose geometry를 무조건 낮은 정밀도로 바꾸지 않는다.</p>''')
sec('review','15 · 이해했는지 스스로 확인하기','''<details><summary>Q1. Tiny에서 pose heads를 고정하면 gradient도 끊길까?</summary><p>아니다. weight 업데이트만 막는다. heads 연산을 통해 입력 특징으로 gradient가 전달된다.</p></details><details><summary>Q2. 20 epochs면 새로운 hypothesis를 20번 만들까?</summary><p>아니다. 현재 fixed cache는 같은 hypothesis를 재사용한다. 새 perturbation에는 새 cache가 필요하다.</p></details><details><summary>Q3. Robot 속도만 추가하면 temporal training인가?</summary><p>속도는 두 시점의 정보이지만 현재 신경망에 sequence memory가 생기는 것은 아니다. Previous hypothesis는 이전 pose를 현재 pose로 고치는 supervision을 만들며 각 sample은 독립적으로 학습된다.</p></details><details><summary>Q4. Train loss 0.003이면 translation 오차 3mm인가?</summary><p>그렇지 않다. CAD surface 평균 거리 3mm이며 위치와 회전 오차가 함께 반영된다.</p></details><details><summary>Q5. 9개 validation에서 가장 좋은 모델이면 최종 test 성능인가?</summary><p>아니다. 그 데이터로 모델을 선택했으므로 독립 test가 아니다.</p></details><details><summary>Q6. 5080에서 Isaac Sim이 실행되면 학습 환경도 준비된 걸까?</summary><p>아니다. FoundationPose의 PyTorch·CUDA·native extension·weights와 실제 rendering gate를 확인해야 한다.</p></details>''')
sec('references','16 · 근거와 더 읽을 자료','''<ul><li><a href="https://github.com/mjcha924/Robot-Aware-Foundation-Pose/tree/feat/omy-training-ready">우리 학습 준비 브랜치</a> — 이 문서가 설명하는 실행 코드.</li><li><a href="https://github.com/mjcha924/Robot-Aware-Foundation-Pose/blob/c23b37976ed1ad3d5f48022fd071d2fa49e21a00/docs/omy_tracking/PIPELINE_HANDOVER.md">OMY 데이터 인계 기록</a> — 데이터 규모·입력 경계·원본 위치.</li><li><a href="https://github.com/NVlabs/FoundationPose/tree/a1b694b83e633c2cb6115b9063d940a687759392">FoundationPose pinned source</a> — 우리가 재사용하는 visual encoder·heads·renderer.</li><li><a href="https://arxiv.org/abs/2312.08344">FoundationPose 논문</a> — 기반 방법과 평가 배경.</li><li><a href="https://arxiv.org/abs/1706.02413">PointNet++</a> — local set abstraction 아이디어.</li><li><a href="https://github.com/brown-ivl/v-hop">V-HOP</a> — 관련 geometry fusion 및 학습 흐름 참고. 이 코드가 V-HOP 재현이라는 뜻은 아니다.</li><li><a href="https://pytorch.org/blog/pytorch-2-7/">PyTorch Blackwell 지원 도입</a> — 5080 환경을 옛 CUDA 조합과 구분해야 하는 근거. 특정 FoundationPose 환경의 호환성을 보증하지 않는다.</li></ul><p class="small">작성 기준: 2026-11-24 · 외부 폰트·스크립트·이미지 없이 구성한 단일 파일. 명령 복사 버튼이 브라우저 권한 때문에 작동하지 않으면 코드를 직접 선택해 복사한다. GitHub는 HTML을 소스로 표시할 수 있으므로 다운로드한 파일을 브라우저에서 연다.</p>''')
# Render the current review/experiment guide into the same offline HTML.
def render_markdown_fragment(markdown):
    rendered=[]
    for index,part in enumerate(markdown.split('```')):
        if index%2:
            rendered.append(pre(part.split('\n',1)[1] if '\n' in part else part))
        else:
            for block in part.strip().split('\n\n'):
                if not block.strip(): continue
                if block.startswith('## '): rendered.append('<h3>'+inline(block[3:])+'</h3>')
                elif not block.startswith('# '): rendered.append('<p>'+inline(block).replace('\n',' ')+'</p>')
    return ''.join(rendered)
experiment=(root/'docs/OMY_MOTION_BASELINE_EXPERIMENTS.md').read_text(encoding='utf-8')
chapters=re.split(r'(?m)(?=^## )',experiment)[1:]
sec('review-fixes','17 · 코드 리뷰에서 수정한 문제',render_markdown_fragment(chapters[0]))
sec('motion-baseline','18 · 기구학 prior를 식과 비교군으로 이해하기',render_markdown_fragment('\n\n'.join(chapters[1:3])))
sec('experiment-order','19 · 지금 실행할 실험 순서와 명령어',render_markdown_fragment('\n\n'.join(chapters[3:8])))
sec('research-next','20 · 결과로 연구 방향을 판단하기',render_markdown_fragment('\n\n'.join(chapters[8:])))

sec('tracking-visualization','21 · 추적 결과를 영상으로 확인하기',render_markdown_fragment((root/'docs/OMY_TRACKING_VISUALIZATION.md').read_text(encoding='utf-8')))

for section_id, title, source in [
 ('pose-math','22 · 좌표계와 pose: 필요한 수학부터','22_pose_math.html'),
 ('learning-math','23 · Loss와 gradient: 숫자로 따라가는 학습','23_learning_math.html'),
 ('architecture-detail','24 · Encoder와 attention을 코드에 연결하기','24_architecture_detail.html'),
 ('first-run','25 · 처음 학습할 때의 관문과 파일 읽기','25_first_run.html'),
 ('study-path','26 · 공부 순서와 정확성 검토 기록','26_study_path.html'),
 ('validation-results','27 · 5080 검증 결과: FK 감사와 CAD-only 대조','27_validation_results.html')]:
 sec(section_id,title,(root/'docs/guide'/source).read_text(encoding='utf-8'))

style='''*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:#f5f3ee;color:#192b36;font:16px/1.85 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:#155b76}nav{position:fixed;inset:0 auto 0 0;width:254px;background:#142d38;color:#e9f1f1;padding:28px 24px;overflow:auto}nav strong{font-size:21px;display:block;line-height:1.4;margin-bottom:22px}nav a{display:block;color:#cfdbdf;text-decoration:none;font-size:13px;padding:8px 0;border-bottom:1px solid #ffffff14}main{margin-left:254px;max-width:1190px;padding:55px 64px 100px}header{padding:12px 0 44px;border-bottom:2px solid #244955}header .eyebrow{letter-spacing:.16em;font-size:12px;color:#426776}h1{font-size:44px;line-height:1.25;letter-spacing:-.045em;margin:18px 0}h2{font-size:26px;line-height:1.45;margin:0 0 24px;letter-spacing:-.035em}h3{font-size:20px;margin-top:34px}section{padding:48px 0;border-bottom:1px solid #d4dcd9}p{margin:16px 0}.lead{font-size:21px}strong{font-weight:700}.small{font-size:13px;color:#52636b}.callout{border-left:4px solid #ad7426;background:#f1e8d8;padding:17px 22px;margin:26px 0}pre{position:relative;background:#172f3b;color:#e9f2f3;padding:24px 20px;overflow:auto;white-space:pre;font:13px/1.8 ui-monospace,SFMono-Regular,Consolas,monospace;border-radius:8px}p code,td code{background:#e3e8e5;padding:2px 5px;border-radius:4px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;padding:14px 15px;border-bottom:1px solid #d5dfdb}th{background:#e3ebe7;color:#244a55}td:first-child{font-weight:600;min-width:135px}td{overflow-wrap:anywhere}.table{overflow:auto}details{background:#fffdf8;margin:12px 0;padding:16px 20px;border:1px solid #dce3dd;border-radius:6px}summary{cursor:pointer;font-weight:600}button{background:#244e60;color:#fff;border:0;border-radius:5px;padding:10px 14px;cursor:pointer;font:inherit;font-size:13px}button:hover{background:#356b80}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #c58b39;outline-offset:3px}.copy{display:block;margin:4px 0 20px;font-size:12px}.arch{display:grid;grid-template-columns:1fr 1fr;gap:16px}.lane{text-align:center;display:flex;flex-direction:column;gap:8px}.node{background:#e3ece8;border:1px solid #c0d3ca;padding:18px;border-radius:8px;font-size:14px}.frozen{background:#e7ebee;border-color:#c2cbd1}.trained{background:#e5edd9;border-color:#b8c6a1}.merge{grid-column:1/-1;text-align:center}.stepper{background:#e1ebe6;padding:25px;border-radius:8px}#step-label{font-size:22px;font-weight:700}.formula{font:22px/1.8 ui-monospace,monospace;padding:24px;background:#e2e9e5}.controls{display:flex;flex-wrap:wrap;gap:24px}.formula{overflow-x:auto}input[type=range]{width:min(240px,55vw)}.stepper label{flex-wrap:wrap}label{display:flex;gap:12px;align-items:center}input{width:85px;padding:9px;font:inherit;border:1px solid #8ca5a6;border-radius:4px}output{display:block;padding:20px;background:#e4ece6;margin-top:15px;font-weight:600}@media(max-width:900px){nav{position:static;width:auto;padding:20px}nav a{display:inline-block;margin-right:15px}nav strong{margin-bottom:8px}main{margin:0;padding:30px 22px}h1{font-size:33px}.arch{grid-template-columns:1fr}.merge{grid-column:auto}}@media print{nav,button,.controls{display:none}main{margin:0;padding:0;max-width:none}body{background:white;color:black;font-size:11pt}section{break-inside:auto}pre{white-space:pre-wrap;background:#eee;color:black}details>*{display:block}h2,h3{break-after:avoid}.node{break-inside:avoid}}'''
script='''const steps=[['1 / 6 · Batch를 읽는다','FeatureDataset이 cache에서 sample을 읽고 collate가 batch tensor로 묶는다. 원본 영상 rendering은 이 단계에서 반복하지 않는다.'],['2 / 6 · Forward','robot encoder가 32개 token을 만들고, attention이 visual token을 보정한다. heads가 pose correction을 출력한다.'],['3 / 6 · Loss','decode_pose가 correction을 pose에 적용한다. CAD점의 예측 위치와 GT 위치 차이를 평균한다.'],['4 / 6 · Backward','zero_grad로 이전 gradient를 비운 뒤 loss.backward()가 연쇄 미분을 계산한다. frozen weight는 갱신 대상이 아니다.'],['5 / 6 · Update','gradient norm을 제한하고 AdamW가 학습 가능한 weight를 갱신한다. 이것이 한 training step이다.'],['6 / 6 · Epoch 평가와 저장','모든 train batch 뒤 validation을 업데이트 없이 평가한다. best.pt와 last.pt를 저장하고 다음 epoch로 진행한다.']];let step=0;function draw(){document.getElementById('step-label').textContent=steps[step][0];document.getElementById('step-detail').textContent=steps[step][1]}document.getElementById('prev').onclick=()=>{step=(step+5)%6;draw()};document.getElementById('next').onclick=()=>{step=(step+1)%6;draw()};draw();function calc(){const b=Number(document.getElementById('batch').value),e=Number(document.getElementById('epochs').value);document.getElementById('calc').textContent=Number.isInteger(b)&&b>0&&Number.isInteger(e)&&e>0?`Epoch당 train ${Math.ceil(1926/b)} batch / validation ${Math.ceil(478/b)} batch. 총 optimizer update ${Math.ceil(1926/b)*e}번.`:'양의 정수를 입력하세요.'}['batch','epochs'].forEach(id=>document.getElementById(id).addEventListener('input',calc));calc();document.querySelectorAll('pre').forEach(pre=>{const b=document.createElement('button');b.type='button';b.className='copy';b.textContent='코드 복사';b.onclick=async()=>{try{await navigator.clipboard.writeText(pre.innerText);b.textContent='복사됨'}catch(e){b.textContent='코드를 직접 선택해 복사하세요'}setTimeout(()=>b.textContent='코드 복사',2500)};pre.after(b)})'''
script += ''';function toy(){const eta=Number(document.getElementById('toy-lr').value);const w=2*eta;const prediction=2*w;const loss=.5*(prediction-1)**2;document.getElementById('toy-result').textContent=`η=${eta.toFixed(2)} → w=${w.toFixed(2)} → ŷ=${prediction.toFixed(2)} → loss ${loss.toFixed(4)} (업데이트 전 0.5000)`}document.getElementById('toy-lr').addEventListener('input',toy);toy();'''
nav=''.join(f'<a href="#{id}">{html.escape(title)}</a>' for id,title,body in sections)
body=''.join(f'<section id="{id}"><h2>{html.escape(title)}</h2>{body}</section>' for id,title,body in sections)
out='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OMY 첫 학습 — 아키텍처부터 실행과 해석까지</title><style>'+style+'</style></head><body><nav aria-label="목차"><strong>Robot-Aware<br>FoundationPose</strong><span class="small" style="color:#c6d5d7">첫 학습을 위한 실습 노트</span>'+nav+'</nav><main><header><div class="eyebrow">ROBOT VISION · TRAINING COMPANION</div><h1>처음 하는 학습,<br>우리 코드로 이해하기</h1><p>데이터 한 프레임이 loss와 gradient를 거쳐 모델의 변화가 되기까지.<br>OMY · Frozen FoundationPose · Robot encoder · Residual fusion</p><p class="small">2026.11.26 · feat/omy-training-ready · 학습 입문부터 5080 실행까지</p></header>'+body+'</main><script>'+script+'</script></body></html>'
(root/'docs/OMY_TRAINING_GUIDE.html').write_text(out)
print(len(out.encode()),'bytes',len(sections),'sections')
