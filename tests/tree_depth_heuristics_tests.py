from unittest import TestCase

from regparser.tree.depth.derive import Solution
from regparser.tree.depth.heuristics import prefer_multiple_children


class HeuristicsTests(TestCase):
    def test_prefer_multiple_children(self):
        lower_idx = 2   # index in the markers.types array for lower case
        solution1 = {'type0': lower_idx, 'idx0': 0, 'depth0': 0,    # a
                     'type1': lower_idx, 'idx1': 1, 'depth1': 0,    # b
                     'type2': lower_idx, 'idx2': 2, 'depth2': 0,
                     'type3': lower_idx, 'idx3': 3, 'depth3': 0,
                     'type4': lower_idx, 'idx4': 4, 'depth4': 0,
                     'type5': lower_idx, 'idx5': 5, 'depth5': 0,
                     'type6': lower_idx, 'idx6': 6, 'depth6': 0,
                     'type7': lower_idx, 'idx7': 7, 'depth7': 0,    # h
                     'type8': lower_idx, 'idx8': 8, 'depth8': 0}    # i
        solution2 = solution1.copy()
        solution2['type8'] = 5  # index of romans in markers.types
        solution2['idx8'] = 0
        solution2['depth8'] = 1

        solutions = [Solution(solution1), Solution(solution2)]
        solutions = prefer_multiple_children(solutions, 0.5)
        self.assertEqual(solutions[0].weight, 1.0)
        self.assertTrue(solutions[1].weight < solutions[0].weight)
