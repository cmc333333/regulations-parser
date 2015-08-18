"""Namespace for constraints on paragraph depth discovery"""

from regparser.tree.depth import markers


def must_be(value):
    """A constraint that the given variable must matches the value."""
    def inner(var):
        return var == value
    return inner


def type_match(marker):
    """The type of the associated variable must match its marker. Lambda
    explanation as in the above rule."""
    return lambda typ, idx: (
        idx < len(markers.types[typ])
        and markers.types[typ][idx] == marker)


def pairs(prev_typ, prev_depth, typ, depth):
    if typ == markers.no_marker_idx:
        if prev_typ == typ:
            return prev_depth == depth
        else:
            return depth <= prev_depth + 1
    return True


def make_seq_depth(indexes, var_idx):
    def seq_depth(prev_typ, prev_depth, typ, depth):
        dec = depth < prev_depth
        cont = (depth == prev_depth
                and (prev_typ == typ or markers.stars_idx in (typ, prev_typ)))
        incr = (depth == prev_depth + 1
                and (prev_typ != typ or typ == markers.stars_idx))
        return dec or cont or incr
    return seq_depth


def make_same_type(indexes, var_idx):
    def same_type(typ, depth, *all_prev):
        """Constraints on sequential markers with the same marker type"""
        # Group (type, depth) per marker
        all_prev = [tuple(all_prev[i:i+2]) for i in range(0, len(all_prev), 2)]
        prev_typ, prev_depth = all_prev[-1]
        idx = indexes[var_idx][typ]
        prev_idx = indexes[var_idx-1][prev_typ]

        if typ != prev_typ:
            return True
        # Stars can't be on the same level in sequence. Can only start a new
        # level if the preceding wasn't inline
        elif typ == markers.stars_idx:
            return depth < prev_depth or (prev_idx == 1
                                          and depth == prev_depth + 1)
        elif typ == markers.no_marker_idx or prev_typ == markers.no_marker_idx:
            return depth == prev_depth
        # If this marker matches *any* previous marker, we may be continuing
        # it's sequence
        else:
            for prev_type, prev_idx, prev_depth in _ancestors(
                    all_prev, indexes):
                if (prev_type == typ and prev_depth == depth
                        and idx == prev_idx + 1):
                    return True
        return False
    return same_type


def make_diff_type(indexes, var_idx):
    def diff_type(typ, depth, *all_prev):
        """Constraints on sequential markers with differing types"""
        idx = indexes[var_idx][typ]
        all_prev = [tuple(all_prev[i:i+2]) for i in range(0, len(all_prev), 2)]
        prev_typ, prev_depth = all_prev[-1]
        prev_idx = indexes[var_idx-1][prev_typ]

        # ... or the previous marker's type matches (see same_type)
        if typ == all_prev[-1][0]:
            return True
        # Starting a new type
        elif idx == 0 and depth == prev_depth + 1:
            return True
        # Stars can't skip levels forward (e.g. _ *, _ _ _ *)
        elif typ == markers.stars_idx:
            return prev_depth - depth >= -1
        # If following stars and on the same level, we're good
        elif prev_typ == markers.stars_idx and depth == prev_depth:
            return True     # Stars
        elif typ == markers.no_marker_idx:
            return depth <= prev_depth + 1
        # If this marker matches *any* previous marker, we may be continuing
        # it's sequence
        else:
            for prev_type, prev_idx, prev_depth in _ancestors(
                    all_prev, indexes):
                if (prev_type == typ and prev_depth == depth
                        and idx == prev_idx + 1):
                    return True
        return False
    return diff_type


def mk_same_depth_same_type(indexes):
    def same_depth_same_type(*all_vars):
        """All markers in the same level (with the same parent) should have
        the same marker type"""
        elements = [(all_vars[i], indexes[i/2][all_vars[i]], all_vars[i+1])
                    for i in range(0, len(all_vars), 2)]

        def per_level(elements, last_type=None):
            level, grouped_children = _level_and_children(elements)

            if not level:
                return True     # Base Case

            types = set(el[0] for el in level)
            types = list(sorted(types, key=lambda t: t == markers.stars_idx))
            if len(types) > 2:
                return False
            if len(types) == 2 and markers.stars_idx not in types:
                return False
            if last_type in types and last_type != markers.stars_idx:
                return False
            for children in grouped_children:           # Recurse
                if not per_level(children, types[0]):
                    return False
            return True

        return per_level(elements)
    return same_depth_same_type


def mk_stars_occupy_space(indexes):
    def stars_occupy_space(*all_vars):
        """Star markers can't be ignored in sequence, so 1, *, 2 doesn't make
        sense for a single level, unless it's an inline star. In the inline
        case, we can think of it as 1, intro-text-to-1, 2"""
        elements = [(all_vars[i], indexes[i/2][all_vars[i]], all_vars[i+1])
                    for i in range(0, len(all_vars), 2)]

        def per_level(elements):
            level, grouped_children = _level_and_children(elements)

            if not level:
                return True     # Base Case

            last_idx = -1
            for typ, idx, depth in level:
                if typ == markers.stars_idx:
                    if idx == 0:    # STARS_TAG, not INLINE_STARS
                        last_idx += 1
                elif last_idx >= idx and typ != markers.no_marker_idx:
                    return False
                else:
                    last_idx = idx

            for children in grouped_children:           # Recurse
                if not per_level(children):
                    return False
            return True

        return per_level(elements)
    return stars_occupy_space


def no_marker_sandwich(pprev_typ, pprev_depth, prev_typ, prev_depth, typ,
                       depth):
    return not (prev_typ == markers.no_marker_idx
                and pprev_depth == prev_depth - 1
                and prev_depth == depth - 1)


def depth_type_order(order):
    """Create a function which constrains paragraphs depths to a particular
    type sequence. For example, we know a priori what regtext and
    interpretation markers' order should be. Adding this constrain speeds up
    solution finding."""
    order = list(order)     # defensive copy

    def inner(constrain, all_variables):
        for i in range(0, len(all_variables) / 3):
            constrain(lambda d: d < len(order), ["depth" + str(i)])
            constrain(lambda t, d: (t == markers.stars_idx
                                    or markers.types[t] == order[d]
                                    or markers.types[t] in order[d]),
                      ("type" + str(i), "depth" + str(i)))

    return inner


def unique_type_per_depth(*all_vars):
    """The same marker type cannot reappear at multiple depths."""
    depth_by_type = {}
    for i in range(0, len(all_vars), 2):
        typ, depth = all_vars[i], all_vars[i+1]
        if typ not in (markers.stars_idx, markers.no_marker_idx):
            if typ not in depth_by_type:
                depth_by_type[typ] = depth
            elif depth_by_type[typ] != depth:
                return False
    return True


def _ancestors(all_prev, indexes):
    """Given an assignment of values, construct a list of the relevant
    parents, e.g. 1, i, a, ii, A gives us 1, ii, A"""
    result = [None]*10
    for i, prev in enumerate(all_prev):
        prev_typ, prev_depth = prev
        prev_idx = indexes[i][prev_typ]

        result[prev_depth] = (prev_typ, prev_idx, prev_depth)
        result[prev_depth + 1:] = [None]*(10 - prev_depth)
    result = filter(bool, result)
    return result


def _level_and_children(elements):
    """Split a list of elements into elements on the current level (i.e.
    that share the same depth as the first element) and segmented children
    (children of each of those elements)"""
    if not elements:        # Base Case
        return [], []
    level_depth = elements[0][2]
    level = []
    grouped_children = []
    children = []

    for el in elements:
        if level_depth == el[2]:
            level.append(el)
            if children:
                grouped_children.append(children)
            children = []
        else:
            children.append(el)
    if children:
        grouped_children.append(children)

    return level, grouped_children
