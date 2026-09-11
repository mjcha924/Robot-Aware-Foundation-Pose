import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from foundationpose_adapter.transforms import effector_object_transform, matmul4, rigid_inverse


class TransformTests(unittest.TestCase):
    def test_rigid_inverse_round_trip(self):
        transform = [
            [0.0, -1.0, 0.0, 1.0],
            [1.0, 0.0, 0.0, 2.0],
            [0.0, 0.0, 1.0, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        identity = matmul4(transform, rigid_inverse(transform))
        for row in range(4):
            for column in range(4):
                self.assertAlmostEqual(identity[row][column], 1.0 if row == column else 0.0)

    def test_effector_object_chain(self):
        identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        world_effector = [row[:] for row in identity]
        world_effector[0][3] = 1.0
        world_camera = [row[:] for row in identity]
        world_camera[1][3] = 2.0
        camera_object = [row[:] for row in identity]
        camera_object[2][3] = 3.0
        result = effector_object_transform(world_effector, world_camera, camera_object)
        self.assertEqual([result[index][3] for index in range(3)], [-1.0, 2.0, 3.0])

    def test_rejects_wrong_shape(self):
        with self.assertRaises(ValueError):
            rigid_inverse([[1.0]])


if __name__ == "__main__":
    unittest.main()
