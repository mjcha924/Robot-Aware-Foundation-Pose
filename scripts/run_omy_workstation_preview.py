"""Launch the configured workstation preview, headless unless --gui is passed."""
import argparse
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', type=Path, default=root / 'configs/omy_tracking/preview.json')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--gui', action='store_true')
args = parser.parse_args()
config = json.loads(args.config.read_text())
command = [config['python'], str(root / 'scripts/preview_omy_workstation.py'),
           '--output', str(args.output.resolve()), '--robot-usd', config['robot_usd'],
           '--background-config', str(args.config.resolve())]
if config.get('environment_usd'):
    command += ['--environment-usd', config['environment_usd']]
if config.get('target_usd'):
    command += ['--target-usd', config['target_usd']]
if not args.gui:
    command.append('--headless')
# User explicitly accepted this license during runtime setup.
env = dict(os.environ, OMNI_KIT_ACCEPT_EULA='YES')
result = subprocess.call(command, env=env, cwd=root)
expected = ['overview.png', 'sensor.png', 'workstation.usda', 'table_bounds.json']
if result == 0 and any(not (args.output / name).is_file() for name in expected):
    raise SystemExit('Preview did not produce all required artifacts; inspect the simulator log.')
raise SystemExit(result)
