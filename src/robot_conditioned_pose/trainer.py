"""Training on cached frozen visual tokens; rendering stays outside autograd."""
import json
import random
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from .model import RobotConditionedRefiner
from .geometry import decode_pose, pose_loss
from .data import FeatureDataset, collate, check_splits
from .contracts import portable_provenance


class CachedHeads(nn.Module):
    """Exact head architecture of pinned upstream RefineNet (axis_angle only).

    Loaded strictly from upstream state_dict; no fabricated pretrained weights.
    """
    def __init__(self):
        super().__init__()
        self.encodeA = nn.Identity()
        self.encodeAB = nn.Identity()
        for name in ('trans_head', 'rot_head'):
            setattr(self, name, nn.Sequential(nn.TransformerEncoderLayer(
                d_model=512, nhead=4, dim_feedforward=512, batch_first=True), nn.Linear(512, 3)))


def device_batch(batch, device):
    return {k: [v.to(device) for v in value] if k == 'symmetries' else value.to(device)
            for k, value in batch.items()}


def batch_loss(model, b, cfg):
    output = model.forward_tokens(b['visual'], b['points'])
    pose = decode_pose(output, b['hypothesis'], b['diameter'], cfg)
    return pose_loss(pose, b['target'], b['cad'], b['symmetries'])


def run(args):
    if args.epochs < 1 or args.batch_size < 1 or args.warmup_epochs < 0:
        raise ValueError('invalid training counts')
    torch.manual_seed(args.seed); np.random.seed(args.seed); random.seed(args.seed)
    train, val = FeatureDataset(args.train), FeatureDataset(args.val)
    check_splits(train, val)
    root = Path(args.output); root.mkdir(parents=True, exist_ok=False)
    cfg = train.manifest['cfg']
    base = CachedHeads()
    base.load_state_dict(torch.load(Path(args.train) / 'heads.pt', weights_only=True, map_location='cpu'), strict=True)
    model = RobotConditionedRefiner(base, mode=args.mode).to(args.device)
    head_params = list(base.trans_head.parameters()) + list(base.rot_head.parameters())
    head_ids = {id(p) for p in head_params}
    new_params = [p for p in model.parameters() if id(p) not in head_ids and p.requires_grad]
    opt = torch.optim.AdamW([{'params': new_params, 'lr': args.lr},
                             {'params': head_params, 'lr': args.head_lr}])
    start, best = 0, float('inf')
    if args.resume:
        ckpt = torch.load(args.resume, map_location=args.device, weights_only=True)
        if ckpt['mode'] != args.mode or portable_provenance(ckpt['provenance']) != portable_provenance(train.manifest):
            raise ValueError('resume mode/data provenance mismatch')
        model.load_state_dict(ckpt['model']); opt.load_state_dict(ckpt['optimizer'])
        start, best = ckpt['epoch'] + 1, ckpt['best']
        torch.set_rng_state(ckpt['rng_cpu'].cpu())
        if args.device.startswith('cuda') and ckpt['rng_cuda']:
            torch.cuda.set_rng_state_all([s.cpu() for s in ckpt['rng_cuda']])
    (root / 'run.json').write_text(json.dumps(vars(args), indent=2))
    train_loader = DataLoader(train, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    val_loader = DataLoader(val, batch_size=args.batch_size, collate_fn=collate)
    for epoch in range(start, args.epochs):
        model.train()
        model.set_head_training(epoch >= args.warmup_epochs)
        if args.mode == 'visual' and epoch < args.warmup_epochs:
            raise ValueError('visual mode requires warmup_epochs=0')
        if args.device.startswith('cuda'):
            torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize()
        epoch_start = time.perf_counter()
        total = 0.
        for raw in train_loader:
            b = device_batch(raw, args.device)
            opt.zero_grad(set_to_none=True)
            loss = batch_loss(model, b, cfg)
            if not torch.isfinite(loss):
                raise RuntimeError('non-finite training loss')
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
            opt.step()
            total += loss.item() * len(b['visual'])
        model.eval(); valid = 0.
        with torch.no_grad():
            for raw in val_loader:
                b = device_batch(raw, args.device)
                loss = batch_loss(model, b, cfg)
                if not torch.isfinite(loss):
                    raise RuntimeError('non-finite validation loss')
                valid += loss.item() * len(b['visual'])
        valid /= len(val)
        improved = valid < best; best = min(best, valid)
        if args.device.startswith('cuda'): torch.cuda.synchronize()
        record = dict(seconds=time.perf_counter()-epoch_start, peak_cuda_bytes=torch.cuda.max_memory_allocated() if args.device.startswith('cuda') else 0, epoch=epoch, train_surface_error_m=total / len(train), val_surface_error_m=valid)
        print(json.dumps(record), flush=True)
        with (root / 'metrics.jsonl').open('a') as f:
            f.write(json.dumps(record) + '\n')
        ckpt = dict(model=model.state_dict(), optimizer=opt.state_dict(), epoch=epoch, best=best,
                    mode=args.mode, cfg=cfg, provenance=train.manifest,
                    rng_cpu=torch.get_rng_state(), rng_cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [])
        torch.save(ckpt, root / 'last.pt')
        if improved:
            torch.save(ckpt, root / 'best.pt')
