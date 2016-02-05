# -*- coding: utf-8 -*-
import pyparsing

from regparser.citations import remove_citation_overlaps
from regparser.grammar import unified
from regparser.tree.depth import markers as mtypes
from regparser.tree.paragraph import p_level_of, p_levels
from regparser.tree.xml_parser import tree_utils


class RegtextMarker(object):
    """A container for representations of regtext paragraph markers.
    @param char: the short (usually one character) identifier
    @param text: the full marker, including parentheses, periods, etc.
    e.g. RegtextMarker('ii', '(ii)') or RegtextMarker('b', '(b) - (d)')"""
    def __init__(self, char, text=''):
        self.char = char
        self.text = text

    def __cmp__(self, other):
        return (self.char, self.text) < (other.char, other.text)

    def deeper_than(self, other):
        """Based a known regtext hierarchy, is `self` on a deeper level than
        `other`"""
        for level1 in p_level_of(self.char):
            for level2 in p_level_of(other.char):
                if level1 > level2:
                    return True
        return False

    @property
    def plain_text(self):
        """Remove any emphasis tags around self.text. Useful when searching
        only the plain text of a node"""
        return self.text.replace('<E T="03">', '').replace('</E>', '')

    @classmethod
    def from_char(cls, char):
        """Shorthand constructor, as most regtext paragraphs will just have
        parens around them"""
        return cls(char, '({})'.format(char))


def _any_depth_parse(match):
    """Convert an any_depth_p match into the appropriate RegtextMarker"""
    markers = [match.p1, match.p2, match.p3, match.p4, match.p5, match.p6]
    for idx in (4, 5):
        if markers[idx]:
            markers[idx] = '<E T="03">{}</E>'.format(markers[idx])
    return [RegtextMarker.from_char(m) for m in markers if m]


any_depth_p = unified.any_depth_p.copy().setParseAction(_any_depth_parse)


def initial_markers(text):
    """Pull out a list of the first paragraph markers, i.e. markers before any
    text"""
    try:
        return list(any_depth_p.parseString(text))
    except pyparsing.ParseException:
        return []


_collapsed_grammar = (
    # A guard to reduce false positives
    pyparsing.Suppress(pyparsing.Regex(u',|\.|-|—|>')) +
    any_depth_p)


def collapsed_markers(text):
    """Not all paragraph markers are at the beginning of of the text. This
    grabs inner markers like (1) and (i) here:
    (c) cContent —(1) 1Content (i) iContent"""
    potential = [triplet for triplet in _collapsed_grammar.scanString(text)]
    #   remove any that overlap with citations
    potential = [trip for trip in remove_citation_overlaps(text, potential)]
    #   flatten the results
    potential = [pm for pms, _, _ in potential for pm in pms]
    #   remove any matches that aren't (a), (1), (i), etc. -- All other
    #   markers can't be collapsed
    first_markers = [level[0] for level in p_levels]
    potential = [pm for pm in potential if pm.char in first_markers]

    return potential


def _continues_collapsed(first, second):
    """Does the second marker continue a sequence started by the first?"""
    if second == mtypes.STARS_TAG:  # Missing data - proceed optimistically
        return True
    for level1, markers1 in enumerate(p_levels):
        for level2, markers2 in enumerate(p_levels):
            if first not in markers1 or second not in markers2:
                continue
            idx1, idx2 = markers1.index(first), markers2.index(second)
            extending = level1 == level2 and idx2 == idx1 + 1
            new_level = level2 == level1 + 1 and idx2 == 0
            if extending or new_level:
                return True
    return False


def get_markers(text, next_marker=None):
    """ Extract all the paragraph markers from text. Do some checks on the
    collapsed markers."""
    initial = initial_markers(text)
    if next_marker is None:
        collapsed = []
    else:
        collapsed = collapsed_markers(text)

    #   Check that the collapsed markers make sense:
    #   * at least one level below the initial marker
    #   * followed by a marker in sequence
    if initial and collapsed:
        collapsed = [c for c in collapsed if c.deeper_than(initial[-1])]
        for marker in reversed(collapsed):
            if _continues_collapsed(marker.char, next_marker.char):
                break
            else:
                collapsed.pop()

    return initial + collapsed


def next_marker(xml):
    """Find the first marker in a paragraph that follows this xml node.
    May return None"""
    good_tags = ('P', 'FP', mtypes.STARS_TAG)

    node = xml.getnext()
    while node is not None and node.tag not in good_tags:
        node = node.getnext()

    if getattr(node, 'tag', None) == mtypes.STARS_TAG:
        return RegtextMarker(mtypes.STARS_TAG)
    elif node is not None:
        tagged_text = tree_utils.get_node_text_tags_preserved(node)
        markers = get_markers(tagged_text.strip())
        if markers:
            return markers[0]


def split_by_markers(xml):
    """Given an xml node, pull out triplets of
        (RegtextMarker, plain text, text-with-tags)
    for each subparagraph found"""
    plain_text = tree_utils.get_node_text(xml, add_spaces=True).strip()
    tagged_text = tree_utils.get_node_text_tags_preserved(xml).strip()
    markers_list = get_markers(tagged_text, next_marker(xml))

    node_texts = tree_utils.split_text(
        plain_text, [m.plain_text for m in markers_list])
    tagged_texts = tree_utils.split_text(
        tagged_text, [m.text for m in markers_list])
    if len(node_texts) > len(markers_list):     # due to initial MARKERLESS
        markers_list.insert(0, RegtextMarker(mtypes.MARKERLESS))
    return zip(markers_list, node_texts, tagged_texts)
