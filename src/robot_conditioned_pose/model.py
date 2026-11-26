"""Local PointNet++-style set abstraction and residual cross-attention.

Tensor-only reference backend, no additional custom CUDA extension. Hierarchical
sampling/grouping follows Qi et al., PointNet++ (2017); independently implemented.
"""
import torch
from torch import nn


def gather(points, indices):
    batch = torch.arange(points.shape[0], device=points.device)
    return points[batch.reshape((-1,) + (1,) * (indices.ndim - 1)), indices]


@torch.no_grad()
def farthest_points(xyz, count):
    count = min(count, xyz.shape[1])
    chosen = torch.zeros((len(xyz), count), dtype=torch.long, device=xyz.device)
    distance = torch.full(xyz.shape[:2], float('inf'), device=xyz.device)
    current = (xyz - xyz.mean(1, keepdim=True)).square().sum(-1).argmax(-1)
    for i in range(count):
        chosen[:, i] = current
        center = gather(xyz, current[:, None])
        distance = torch.minimum(distance, (xyz - center).square().sum(-1))
        current = distance.argmax(-1)
    return chosen


class SetAbstraction(nn.Module):
    def __init__(self, feature_dim, width, count, radius, neighbors=16):
        super().__init__()
        self.count, self.radius, self.neighbors = count, radius, neighbors
        self.mlp = nn.Sequential(nn.Linear(feature_dim + 3, width), nn.LayerNorm(width),
                                 nn.GELU(), nn.Linear(width, width), nn.GELU())

    def forward(self, xyz, features):
        centers = gather(xyz, farthest_points(xyz, self.count))
        distance = torch.cdist(centers, xyz)
        distances, idx = distance.topk(min(self.neighbors, xyz.shape[1]), largest=False)
        valid = distances <= self.radius
        local = torch.cat((gather(xyz, idx) - centers[:, :, None], gather(features, idx)), -1)
        encoded = self.mlp(local).masked_fill(~valid[..., None], -torch.inf)
        return centers, encoded.max(2).values  # centers are sampled points: >=1 valid neighbor


class RobotEncoder(nn.Module):
    def __init__(self, dim=512, counts=(128, 32)):
        super().__init__()
        self.sa1 = SetAbstraction(8, 64, counts[0], .15)
        self.sa2 = SetAbstraction(64, 128, counts[1], .35)
        self.project = nn.Linear(128, dim)
        self.position = nn.Sequential(nn.Linear(3, dim), nn.GELU(), nn.Linear(dim, dim))

    def forward(self, points):
        if points.ndim != 3 or points.shape[-1] != 11 or points.shape[1] == 0:
            raise ValueError('expected nonempty [B,P,11] point features')
        if not torch.isfinite(points).all():
            raise ValueError('non-finite points')
        xyz, features = self.sa1(points[..., :3], points[..., 3:])
        xyz, features = self.sa2(xyz, features)
        return self.project(features) + self.position(xyz)


MODES = ('visual', 'cad-only', 'geometry', 'motion')


def select_cad_rows(points):
    """Keep only object-CAD rows (is_robot channel 9 == 0), in their original order.

    Rows are chosen by the flag, never by position. CAD xyz/normal and their
    original zero robot-flag/velocity/validity channels are kept unchanged; no
    robot rows are zeroed, padded or moved. Every sample must hold the same
    nonzero number of CAD rows so the batch stays rectangular.
    """
    flag = points[..., 9]
    if not torch.all((flag == 0) | (flag == 1)):
        raise ValueError('is_robot channel must be exactly 0 or 1')
    cad = flag == 0
    counts = cad.sum(1)
    if (counts == 0).any() or (counts != counts[0]).any():
        raise ValueError(f'cad-only needs the same nonzero CAD row count per sample, got {counts.tolist()}')
    return points[cad].reshape(points.shape[0], int(counts[0]), points.shape[-1])


class RobotConditionedRefiner(nn.Module):
    def __init__(self, upstream, dim=512, counts=(128, 32), mode='motion'):
        super().__init__()
        if mode not in MODES:
            raise ValueError(mode)
        self.upstream, self.mode = upstream, mode
        self.robot_encoder = RobotEncoder(dim, counts)
        self.visual_norm, self.robot_norm = nn.LayerNorm(dim), nn.LayerNorm(dim)
        self.attention = nn.MultiheadAttention(dim, 4, batch_first=True, dropout=0)
        self.residual_scale = nn.Parameter(torch.tensor(.01))
        for name in ('encodeA', 'encodeAB'):
            getattr(self.upstream, name).requires_grad_(False)
        self.train()

    def train(self, mode=True):
        super().train(mode)
        self.upstream.encodeA.eval()
        self.upstream.encodeAB.eval()
        return self

    def set_head_training(self, enabled):
        self.upstream.trans_head.requires_grad_(enabled)
        self.upstream.rot_head.requires_grad_(enabled)

    @torch.no_grad()
    def encode_visual(self, a, b):
        n = len(a)
        shared = self.upstream.encodeA(torch.cat((a, b), 0))
        paired = self.upstream.encodeAB(torch.cat((shared[:n], shared[n:]), 1).contiguous())
        return self.upstream.pos_embed(paired.flatten(2).transpose(1, 2))

    def forward_tokens(self, visual, points, bypass=False):
        fused = visual
        if self.mode != 'visual' and not bypass:
            if self.mode == 'geometry':
                points = points.clone()
                points[..., 6:9] = 0
                points[..., 10] = 0
            elif self.mode == 'cad-only':
                # Same encoder/fusion/heads as geometry; the robot rows are absent.
                points = select_cad_rows(points)
            robot = self.robot_norm(self.robot_encoder(points))
            extra, _ = self.attention(self.visual_norm(visual), robot, robot, need_weights=False)
            fused = visual + self.residual_scale * extra
        return {'trans': self.upstream.trans_head(fused).mean(1),
                'rot': self.upstream.rot_head(fused).mean(1)}

    def forward(self, a, b, points, bypass=False):
        return self.forward_tokens(self.encode_visual(a, b), points, bypass)
