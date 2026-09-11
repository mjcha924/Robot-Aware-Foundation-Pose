"""Small, dependency-free helpers for rigid 4x4 transforms."""

from __future__ import annotations

from typing import List, Sequence


Matrix4 = List[List[float]]


def as_matrix4(value: Sequence[Sequence[float]]) -> Matrix4:
    """Return *value* as a finite-looking 4x4 float matrix.

    Rigidity is deliberately checked by the export validator. This helper only
    enforces the shape required by composition code.
    """

    if len(value) != 4 or any(len(row) != 4 for row in value):
        raise ValueError("expected a 4x4 matrix")
    return [[float(item) for item in row] for row in value]


def matmul4(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]) -> Matrix4:
    """Multiply two 4x4 matrices."""

    a = as_matrix4(left)
    b = as_matrix4(right)
    return [[sum(a[row][k] * b[k][column] for k in range(4)) for column in range(4)] for row in range(4)]


def rigid_inverse(transform: Sequence[Sequence[float]]) -> Matrix4:
    """Invert a rigid transform without a numerical linear-algebra package."""

    matrix = as_matrix4(transform)
    rotation_t = [[matrix[column][row] for column in range(3)] for row in range(3)]
    translation = [matrix[row][3] for row in range(3)]
    result: Matrix4 = [[0.0] * 4 for _ in range(4)]
    for row in range(3):
        result[row][:3] = rotation_t[row]
        result[row][3] = -sum(rotation_t[row][column] * translation[column] for column in range(3))
    result[3][3] = 1.0
    return result


def effector_object_transform(
    t_world_effector: Sequence[Sequence[float]],
    t_world_camera: Sequence[Sequence[float]],
    t_camera_object: Sequence[Sequence[float]],
) -> Matrix4:
    """Compute ``T_effector_object`` from the export contract transforms."""

    return matmul4(rigid_inverse(t_world_effector), matmul4(t_world_camera, t_camera_object))
