"""Bounded dynamics gate before workstation sequence capture."""
import argparse
import json
import sys
import traceback
from pathlib import Path
from isaacsim import SimulationApp

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cyclo-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--device', default='cuda:0')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
app = SimulationApp({'headless': True})
try:
    import torch
    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation
    sys.path.insert(0, str(args.cyclo_root / 'source/cyclo_lab'))
    from cyclo_lab.assets.robots.OMY import OMY_CFG
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=1/120, device=args.device))
    cfg = OMY_CFG.replace(prim_path='/World/Robot')
    robot = Articulation(cfg)
    sim.reset()
    q = robot.data.default_joint_pos.clone()
    robot.write_joint_state_to_sim(q, torch.zeros_like(q))
    records = []
    for step in range(240):
        robot.set_joint_position_target(q)
        robot.write_data_to_sim()
        sim.step(render=False)
        robot.update(1/120)
        if step % 30 == 0:
            records.append({'step': step, 'q': robot.data.joint_pos[0].cpu().tolist(), 'root_position': robot.data.root_pos_w[0].cpu().tolist()})
    error = float(torch.max(torch.abs(robot.data.joint_pos-q)))
    report = {'fixed_base': robot.is_fixed_base, 'joint_names': robot.joint_names, 'body_names': robot.body_names, 'max_hold_error_rad': error, 'samples': records, 'passed': bool(robot.is_fixed_base and error < 0.05)}
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report), flush=True)
except Exception:
    traceback.print_exc()
    (args.output/'error.txt').write_text(traceback.format_exc())
finally:
    app.close()
