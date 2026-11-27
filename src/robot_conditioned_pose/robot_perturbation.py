"""Inference-only robot-state corruptions for the robot-state mismatch control.

Only the measured robot state fed to the refiner (joint positions and robot base
pose) is replaced. Camera pose, images, timestamps, object GT and the scoring
path are untouched. Training caches never use this module.
"""
import hashlib
import json
from pathlib import Path
import numpy as np

KINDS = ('none', 'delay', 'zero-velocity', 'freeze-first', 'swap-sequence', 'joint-noise')
NOISE_SEED = 2026


def parse(spec):
    """'none', 'delay-3', 'zero-velocity', 'freeze-first', 'swap-sequence', 'joint-noise-0.02'."""
    for kind in ('delay', 'joint-noise'):
        if spec.startswith(kind+'-'):
            value = float(spec[len(kind)+1:])
            if kind == 'delay' and (value != int(value) or value < 1):
                raise ValueError('delay needs a positive integer frame count')
            if kind == 'joint-noise' and not value > 0:
                raise ValueError('joint-noise needs a positive std in radians')
            return kind, (int(value) if kind == 'delay' else value)
    if spec in ('none', 'zero-velocity', 'freeze-first', 'swap-sequence'):
        return spec, None
    raise ValueError('unknown robot perturbation: '+repr(spec))


def _load_states(sequence):
    sequence = Path(sequence)
    ext = json.loads((sequence/'manifest.json').read_text())['omy_tracking']
    frames = [json.loads(s) for s in (sequence/ext['robot_observations_file']).read_text().splitlines()]
    previous = json.loads((sequence/ext['previous_robot_state_file']).read_text())
    return tuple(ext['joint_names']), frames, previous


class RobotPerturbation:
    def __init__(self, spec, sequence_name, joint_names, donor=None):
        self.spec = spec
        self.kind, self.value = parse(spec)
        self.sequence_name = sequence_name
        self.donor_name = None
        if self.kind == 'swap-sequence':
            if donor is None:
                raise ValueError('swap-sequence needs a donor sequence')
            names, self.donor_frames, self.donor_previous = _load_states(donor)
            if names != tuple(joint_names):
                raise ValueError('donor joint names differ')
            self.donor_name = Path(donor).name
            if self.donor_name == sequence_name:
                raise ValueError('donor must be a different sequence')
        elif donor is not None:
            raise ValueError('only swap-sequence takes a donor')
        self._seed = int(hashlib.sha256(sequence_name.encode()).hexdigest()[:8], 16)

    @property
    def zero_velocity(self):
        return self.kind == 'zero-velocity'

    def state(self, reader, i):
        """Robot state used in place of the measurement at index i (-1 = previous state)."""
        measured = lambda j: reader.previous_state if j < 0 else reader.frames[j]
        if self.kind in ('none', 'zero-velocity'):
            return measured(i)
        if self.kind == 'delay':
            # Before the sequence start only the single stored previous state exists.
            return measured(max(i-self.value, -1))
        if self.kind == 'freeze-first':
            return measured(min(i, 0))
        if self.kind == 'swap-sequence':
            return self.donor_previous if i < 0 else self.donor_frames[min(i, len(self.donor_frames)-1)]
        state = measured(i)
        rng = np.random.default_rng([NOISE_SEED, self._seed, i+1])
        joints = np.asarray(state['joint_positions'], dtype=np.float64)
        return dict(joint_positions=(joints+rng.normal(0., self.value, joints.shape)).tolist(),
                    T_world_robot_base=state['T_world_robot_base'])

    def describe(self):
        return dict(spec=self.spec, kind=self.kind, value=self.value, donor_sequence=self.donor_name,
                    noise_seed=NOISE_SEED if self.kind == 'joint-noise' else None,
                    scope='refiner robot input only (joint positions, robot base); camera, images, timestamps, GT unchanged')
