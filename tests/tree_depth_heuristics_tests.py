from unittest import TestCase

from regparser.tree.depth.derive import Solution
from regparser.tree.depth.heuristics import prefer_multiple_children


class HeuristicsTests(TestCase):
    def test_prefer_multiple_children(self):
        lower_idx = 2   # index in the markers.types array for lower case
        solution1 = {}
        for i in range(9):
            solution1['type{}'.format(i)] = lower_idx
            solution1['idx{}'.format(i)] = i    # a through i
            solution1['depth{}'.format(i)] = 0

        solution2 = solution1.copy()
        solution2['type8'] = 5  # index of romans in markers.types
        solution2['idx8'] = 0   # roman numeral i
        solution2['depth8'] = 1

        solutions = [Solution(solution1), Solution(solution2)]
        solutions = prefer_multiple_children(solutions, 0.5)
        self.assertEqual(solutions[0].weight, 1.0)
        self.assertTrue(solutions[1].weight < solutions[0].weight)
