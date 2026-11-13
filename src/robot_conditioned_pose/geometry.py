"""Column-vector SE(3), metres, OpenCV camera coordinates."""
import torch


def transform(points, pose):
    return points @ pose[..., :3, :3].transpose(-1, -2) + pose[..., None, :3, 3]


def point_features(robot, normals, previous_robot, dt, hypothesis, object_points,
                   object_normals, diameter):
    """Unbatched. Both robot arrays already expressed in the CURRENT camera frame.

    Output channels: xyz/diameter, normal, velocity/diameter (1/s),
    is_robot, velocity_valid. Object velocity is unknown, never ground truth.
    """
    if diameter <= 0 or dt <= 0:
        raise ValueError('diameter and dt must be positive')
    inv = torch.linalg.inv(hypothesis)
    xyz = transform(robot, inv) / diameter
    normal = normals @ inv[:3, :3].T
    valid = previous_robot is not None
    velocity = torch.zeros_like(robot) if not valid else (robot - previous_robot) / dt
    velocity = velocity @ inv[:3, :3].T / diameter
    ones = torch.ones((len(robot), 1), dtype=robot.dtype, device=robot.device)
    r = torch.cat((xyz, normal, velocity, ones, ones * valid), -1)
    zeros = torch.zeros((len(object_points), 5), dtype=robot.dtype, device=robot.device)
    o = torch.cat((object_points / diameter, object_normals, zeros), -1)
    result = torch.cat((r, o))
    if not torch.isfinite(result).all():
        raise ValueError('non-finite point features')
    return result


def axis_angle_matrix(vector):
    """Stable exponential map, including finite gradients at zero."""
    x, y, z = vector.unbind(-1)
    zero = torch.zeros_like(x)
    skew = torch.stack((zero, -z, y, z, zero, -x, -y, x, zero), -1).reshape(-1, 3, 3)
    angle = torch.linalg.vector_norm(vector, dim=-1)
    a = torch.sinc(angle / torch.pi)[:, None, None]
    b = (0.5 * torch.sinc(angle / (2 * torch.pi)).square())[:, None, None]
    eye = torch.eye(3, device=vector.device, dtype=vector.dtype).expand_as(skew)
    return eye + a * skew + b * (skew @ skew)


def decode_pose(output, hypothesis, diameter, cfg):
    """Match upstream tracknet/axis_angle convention; reject unsupported configs."""
    if cfg.get('trans_rep', 'tracknet') != 'tracknet':
        raise ValueError('V1 supports only tracknet translation')
    if cfg.get('rot_rep', 'axis_angle') != 'axis_angle':
        raise ValueError('V1 supports only axis_angle checkpoints')
    t = output['trans'].float()
    if cfg.get('normalize_xyz', False):
        t = t * diameter[:, None] / 2
    else:
        t = t.tanh() * torch.as_tensor(cfg['trans_normalizer'], device=t.device)
    # Upstream so3_exp_map returns row convention then transposes it.
    rotation = axis_angle_matrix(output['rot'].float().tanh() * cfg['rot_normalizer'])
    result = hypothesis.clone()
    result[:, :3, :3] = rotation @ hypothesis[:, :3, :3]
    result[:, :3, 3] = hypothesis[:, :3, 3] + t
    return result


def pose_loss(predicted, target, cad, symmetries):
    """Minimum corresponding-surface error over declared object symmetries.

    symmetries: list of [S,4,4] tensors, including identity; translation included.
    """
    losses = []
    for pred, gt, points, syms in zip(predicted, target, cad, symmetries):
        p = transform(points, pred)
        equivalent = transform(points, gt[None] @ syms)
        losses.append(torch.linalg.vector_norm(p[None] - equivalent, dim=-1).mean(-1).min())
    return torch.stack(losses).mean()
