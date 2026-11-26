#!/usr/bin/env python3
"""Train robot-conditioned heads using prepare_robot_refiner.py feature caches."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--train', required=True)
    p.add_argument('--val', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--mode', choices=['visual', 'cad-only', 'geometry', 'motion'], default='motion')
    p.add_argument('--device', default='cuda')
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--warmup-epochs', type=int, default=0)
    p.add_argument('--batch-size', type=int, default=4)
    p.add_argument('--lr', type=float, default=1e-4)
    p.add_argument('--head-lr', type=float, default=1e-5)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--resume')
    p.add_argument('--no-tensorboard', dest='tensorboard', action='store_false',
                   help='Do not write <output>/tensorboard event files (logging only)')
    from robot_conditioned_pose.trainer import run
    run(p.parse_args())
