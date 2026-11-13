"""Measure physical-grasp diagnostics; this does not accept a dataset sequence."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation


def assess(root):
    data = json.loads((root / 'diagnostics.json').read_text())
    rows = data['frames']
    target = np.array([r['target_usd_world'] for r in rows])
    effector = np.array([r['T_world_effector'] for r in rows])
    relative = np.linalg.inv(effector) @ target
    holds = [i for i, r in enumerate(rows) if r['phase'] == 'lift']
    # The final second of the lift phase is the candidate stable hold.
    indices = holds[-30:]
    hold = None
    if len(indices) == 30:
        samples = relative[indices]
        hold = {
            'start_frame': indices[0], 'end_frame': indices[-1],
            'minimum_height_above_initial_m': float((target[indices, 2, 3] - target[0, 2, 3]).min()),
            'relative_translation_range_m': float(np.linalg.norm(samples[:, :3, 3] - samples[0, :3, 3], axis=1).max()),
            'relative_rotation_range_deg': float(np.rad2deg(Rotation.from_matrix(samples[:, :3, :3] @ samples[0, :3, :3].T).magnitude()).max()),
        }
        hold['passed_diagnostic'] = (hold['minimum_height_above_initial_m'] >= .05
                                    and hold['relative_translation_range_m'] <= .01
                                    and hold['relative_rotation_range_deg'] <= 10)
    from collections import Counter
    report = {'accepted_pilot_sequence': False, 'phase_frames': dict(Counter(r['phase'] for r in rows)),
              'maximum_origin_lift_m': float(target[:, 2, 3].max()-target[0, 2, 3]),
              'hold': hold, 'note': 'Origin lift and stable hold are diagnostic only; full acceptance is separate.'}
    if 'validation_contact_normal_forces_N' in rows[0]:
        forces = np.array([r['validation_contact_normal_forces_N'] for r in rows])
        report['peak_contact_normal_force_N_by_body'] = dict(zip(data['contact_body_order'], np.linalg.norm(forces, axis=-1).max(axis=(0, 2)).tolist()))
    (root / 'grasp_assessment.json').write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    print(json.dumps(assess(args.root), indent=2))
