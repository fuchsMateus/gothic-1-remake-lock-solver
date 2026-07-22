import unittest

from lock_solver import Direction, LockLayerDefinition, LockSolver


class LockSolverTests(unittest.TestCase):
    def test_solves_a_single_layer(self):
        steps = LockSolver([LockLayerDefinition(position=1)]).solve()

        self.assertEqual([StepExpectation(0, Direction.LEFT, 2)], [
            StepExpectation(step.lock_layer_id, step.direction, step.actions) for step in steps
        ])

    def test_solves_positive_link_in_one_move(self):
        steps = LockSolver([
            LockLayerDefinition(position=2, positive_links=(1,)),
            LockLayerDefinition(position=2),
        ]).solve()

        self.assertEqual(0, steps[0].lock_layer_id)
        self.assertEqual(Direction.LEFT, steps[0].direction)
        self.assertEqual(1, steps[0].actions)

    def test_current_java_main_configuration_has_no_solution(self):
        layers = [
            LockLayerDefinition(1, positive_links=(2,), negative_links=(1,)),
            LockLayerDefinition(3),
            LockLayerDefinition(4, positive_links=(1,), negative_links=(4,)),
            LockLayerDefinition(6, positive_links=(5,), negative_links=(2, 1)),
            LockLayerDefinition(4, positive_links=(5,), negative_links=(3,)),
            LockLayerDefinition(4, positive_links=(0,)),
        ]

        self.assertIsNone(LockSolver(layers).solve())


class StepExpectation:
    def __init__(self, layer_id, direction, actions):
        self.layer_id = layer_id
        self.direction = direction
        self.actions = actions

    def __eq__(self, other):
        return (
            self.layer_id == other.layer_id
            and self.direction == other.direction
            and self.actions == other.actions
        )


if __name__ == "__main__":
    unittest.main()
