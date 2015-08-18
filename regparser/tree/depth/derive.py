from constraint import InSetConstraint, Problem

from regparser.tree.depth import markers, rules


class ParAssignment(object):
    """A paragraph's type, index, depth assignment"""
    def __init__(self, typ, idx, depth):
        self.typ = typ
        self.idx = idx
        self.depth = depth


class Solution(object):
    """A collection of assignments + a weight for how likely this solution is
    (after applying heuristics)"""
    def __init__(self, assignment, indexes, weight=1.0):
        self.indexes = indexes
        self.weight = weight
        self.assignment = []
        if isinstance(assignment, list):
            self.assignment = assignment
        else:   # assignment is a dict (as returned by constraint solver)
            for i in range(len(assignment) / 2):    # for (type, depth)
                self.assignment.append(
                    ParAssignment(markers.types[assignment['type' + str(i)]],
                                  indexes[i][assignment['type' + str(i)]],
                                  assignment['depth' + str(i)]))

    def copy_with_penalty(self, penalty):
        """Immutable copy while modifying weight"""
        sol = Solution([], self.indexes, self.weight * (1 - penalty))
        sol.assignment = self.assignment
        return sol

    def __iter__(self):
        return iter(self.assignment)

    def pretty_print(self):
        for par in self.assignment:
            print " "*4*par.depth + par.typ[par.idx]


def derive_depths(marker_list, additional_constraints=[]):
    """Use constraint programming to derive the paragraph depths associated
    with a list of paragraph markers. Additional constraints (e.g. expected
    marker types, etc.) can also be added. Such constraints are functions of
    two parameters, the constraint function (problem.addConstraint) and a
    list of all variables"""
    if not marker_list:
        return []
    problem = Problem()

    # Marker type per marker
    problem.addVariables(["type" + str(i) for i in range(len(marker_list))],
                         range(len(markers.types)))
    # Depth in the tree, with an arbitrary limit of 10
    problem.addVariables(["depth" + str(i) for i in range(len(marker_list))],
                         range(10))
    all_vars = []
    for i in range(len(marker_list)):
        all_vars.extend(['type' + str(i), 'depth' + str(i)])

    # Always start at depth 0
    problem.addConstraint(InSetConstraint([0]), ["depth0"])

    indexes = []
    for idx, marker in enumerate(marker_list):
        index = {}
        for t in range(len(markers.types)):
            typ = markers.types[t]
            if marker in typ:
                index[t] = next(idx for idx in range(len(typ))
                                if typ[idx] == marker)
        indexes.append(index)

        problem.addConstraint(InSetConstraint(index.keys()),
                              ["type{}".format(idx)])

        if idx > 0:
            pair_typ_depth = ["type{}".format(idx-1), "depth{}".format(idx-1),
                              "type{}".format(idx), "depth{}".format(idx)]
            problem.addConstraint(rules.make_seq_depth(indexes, idx),
                                  pair_typ_depth)
            problem.addConstraint(rules.pairs, pair_typ_depth)

        if idx > 1:
            triple = ["type{}".format(idx-2), "depth{}".format(idx-2),
                      "type{}".format(idx-1), "depth{}".format(idx-1),
                      "type{}".format(idx), "depth{}".format(idx)]
            problem.addConstraint(rules.no_marker_sandwich, triple)

    for idx in range(1, len(marker_list)):
        prior_params = all_vars[2*idx:2*(idx+1)]
        prior_params += all_vars[:2*idx]
        problem.addConstraint(rules.make_same_type(indexes, idx), prior_params)
        problem.addConstraint(rules.make_diff_type(indexes, idx), prior_params)

    # @todo: There's probably efficiency gains to making these rules over
    # prefixes (see above) rather than over the whole collection at once
    problem.addConstraint(rules.mk_same_depth_same_type(indexes), all_vars)
    problem.addConstraint(rules.mk_stars_occupy_space(indexes), all_vars)

    for constraint in additional_constraints:
        constraint(problem.addConstraint, all_vars)

    return [Solution(solution, indexes) for solution in problem.getSolutions()]
