"""Prepared feature cache. Trusted local .pt files only; no arbitrary pickle."""
import json
from pathlib import Path
import torch
from torch.utils.data import Dataset


class FeatureDataset(Dataset):
    def __init__(self, root):
        self.root = Path(root)
        self.manifest = json.loads((self.root / 'manifest.json').read_text())
        self.files = self.manifest['samples']
        if not self.files:
            raise ValueError('empty cache')

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        path = (self.root / self.files[idx]).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError('sample outside cache')
        return torch.load(path, map_location='cpu', weights_only=True)


def collate(samples):
    return {k: [s[k] for s in samples] if k == 'symmetries' else
            torch.stack([s[k] for s in samples]) for k in samples[0]}


def check_splits(train, val):
    if set(train.manifest.get('parent_groups', [])) & set(val.manifest.get('parent_groups', [])):
        raise ValueError('train/validation physical parent overlap')
    if train.manifest.get('splits') and set(train.manifest['splits']) - {'train', 'legacy'}:
        raise ValueError('non-train sequence in training cache')
    if val.manifest.get('splits') and set(val.manifest['splits']) - {'validation', 'legacy'}:
        raise ValueError('non-validation sequence in validation cache')
    for key in ('upstream_commit', 'weight_sha256', 'cfg'):
        if train.manifest[key] != val.manifest[key]:
            raise ValueError('cache provenance mismatch: ' + key)
    if set(train.manifest['sequence_ids']) & set(val.manifest['sequence_ids']):
        raise ValueError('train/validation sequence overlap')
