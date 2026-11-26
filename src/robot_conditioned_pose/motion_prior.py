"""Label-free rigid-grasp prior. T_AB maps coordinates in B into A."""
import torch


def validate_pose(pose):
    if (pose.shape != (4, 4) or not torch.isfinite(pose).all()
        or not torch.allclose(pose[3], pose.new_tensor([0, 0, 0, 1]), atol=1e-5)
        or not torch.allclose(pose[:3, :3].T @ pose[:3, :3], torch.eye(3, device=pose.device, dtype=pose.dtype), atol=1e-4)
        or not torch.isclose(torch.linalg.det(pose[:3, :3]), pose.new_tensor(1.), atol=1e-4)):
        raise ValueError('expected finite rigid 4x4 pose')


def propagate_pose(previous_pose, previous_camera, current_camera,
                   previous_effector=None, current_effector=None):
    """Return T_CtM from previous T_CprevM and world camera/effector poses.

    Without effectors this is a static-world hold. With effectors this assumes
    rigid attachment for the entire interval, including noncontact/release.
    There is deliberately no simulator contact gate or hidden GT correction.
    """
    if (previous_effector is None) != (current_effector is None):
        raise ValueError('both effector poses are required')
    # Compose in float64: a pure kinematic rollout re-feeds its own output for
    # hundreds of frames, and float32 inverse/matmul chains drifted the
    # homogeneous row past validate_pose's 1e-5 (frame 274 of asymmetric_B_04).
    dtype = previous_pose.dtype
    previous_pose, previous_camera, current_camera = (
        x.double() for x in (previous_pose, previous_camera, current_camera))
    world_mesh = previous_camera @ previous_pose
    if current_effector is not None:
        world_mesh = current_effector.double() @ torch.linalg.inv(previous_effector.double()) @ world_mesh
    result = torch.linalg.inv(current_camera) @ world_mesh
    result[3] = result.new_tensor([0., 0., 0., 1.])  # exact by definition of a rigid transform
    return result.to(dtype)
