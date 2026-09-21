"""Isaac 5.1 OMY IK adapter: express the PhysX COM Jacobian at the link origin.

Import only after starting the Isaac application. The stock action in the
installed Isaac Lab version combines a COM Jacobian with a link-origin pose.
"""

import torch

from isaaclab.envs.mdp.actions.task_space_actions import DifferentialInverseKinematicsAction
from isaaclab.utils.math import matrix_from_quat, quat_inv, skew_symmetric_matrix


class LinkOriginIKAction(DifferentialInverseKinematicsAction):
    def _compute_frame_jacobian(self):
        if self.cfg.body_offset is not None:
            raise ValueError("LinkOriginIKAction expects link-origin commands with body_offset=None")
        # Clone before rotating/shifting: PhysX owns the source buffer.
        jacobian = self.jacobian_w.clone()
        world_to_base = matrix_from_quat(quat_inv(self._asset.data.root_quat_w))
        jacobian[:, :3] = world_to_base @ jacobian[:, :3]
        jacobian[:, 3:] = world_to_base @ jacobian[:, 3:]
        com_to_link_world = (
            self._asset.data.body_pos_w[:, self._body_idx]
            - self._asset.data.body_com_pos_w[:, self._body_idx]
        )
        com_to_link_base = (world_to_base @ com_to_link_world.unsqueeze(-1)).squeeze(-1)
        # v_link = v_com + omega x (p_link - p_com).
        jacobian[:, :3] -= torch.bmm(skew_symmetric_matrix(com_to_link_base), jacobian[:, 3:])
        return jacobian
