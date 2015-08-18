import logging

from regparser.tree.depth import heuristics, markers as mtypes
from regparser.tree.depth.derive import derive_depths
from regparser.tree.struct import Node
from regparser.tree.xml_parser import tree_utils


class ParagraphProcessor(object):
    """Processing paragraphs in a generic manner requires a lot of state to be
    carried in between xml nodes. Use a class to wrap that state so we can
    compartmentalize processing with various tags. This is an abstract class;
    regtext, interpretations, appendices, etc. should inherit and override
    where needed"""

    # Subclasses should override the following interface
    NODE_TYPE = None
    MATCHERS = []

    def parse_nodes(self, xml):
        """Derive a flat list of nodes from this xml chunk. This does nothing
        to determine node depth"""
        nodes = []

        for child in xml.getchildren():
            matching = (m for m in self.MATCHERS if m.matches(child))
            tag_matcher = next(matching, None)
            if tag_matcher:
                nodes.extend(tag_matcher.derive_nodes(child))

        # Trailing stars don't matter; slightly more efficient to ignore them
        while nodes and nodes[-1].label[0] in mtypes.stars:
            nodes = nodes[:-1]

        return nodes

    def select_depth(self, depths):
        """There might be multiple solutions to our depth processing problem.
        Use heuristics to select one."""
        depths = heuristics.prefer_same_types_same_levels(depths, 0.8)
        depths = heuristics.prefer_diff_types_diff_levels(depths, 0.8)
        depths = heuristics.prefer_multiple_children(depths, 0.4)
        depths = sorted(depths, key=lambda d: d.weight, reverse=True)
        return depths[0]

    def build_hierarchy(self, root, nodes, depths):
        """Given a root node, a flat list of child nodes, and a list of
        depths, build a node hierarchy around the root"""
        cnt = 0   # number of nodes we've seen without a marker
        stack = tree_utils.NodeStack()
        stack.add(0, root)
        for node, par in zip(nodes, depths):
            if par.typ != mtypes.stars:
                # Note that nodes still only have the one label part
                label, cnt = self.clean_label(node.label[0], cnt)
                node.label = [label]
                stack.add(1 + par.depth, node)

        return stack.collapse()

    def clean_label(self, label, unlabeled_counter):
        """There are some artifacts from parsing and deriving the depth that
        we remove here"""
        if label == mtypes.NO_MARKER:
            unlabeled_counter += 1
            label = 'p{0}'.format(unlabeled_counter)

        label = label.replace('<E T="03">', '').replace('</E>', '')
        return label, unlabeled_counter

    def separate_intro(self, nodes):
        """In many situations the first unlabeled paragraph is the "intro"
        text for a section. We separate that out here"""
        labels = [n.label[0] for n in nodes]    # label is only one part long

        only_one = labels == [mtypes.NO_MARKER]
        switches_after_first = (
            len(nodes) > 1
            and labels[0] == mtypes.NO_MARKER
            and labels[1] != mtypes.NO_MARKER)

        if only_one or switches_after_first:
            return nodes[0], nodes[1:]
        else:
            return None, nodes

    def process(self, xml, root):
        nodes = self.parse_nodes(xml)
        intro_node, nodes = self.separate_intro(nodes)
        if intro_node:
            root.text += " " + intro_node.text
            root.tagged_text += " " + intro_node.tagged_text
        if nodes:
            for n in nodes:
                print n.text
            markers = [node.label[0] for node in nodes]
            depths = derive_depths(markers, self.additional_constraints())
            if not depths:
                logging.error(
                    "Could not determine paragraph depths:\n%s", markers)
            depths = self.select_depth(depths)
            return self.build_hierarchy(root, nodes, depths)
        else:
            return root

    def additional_constraints(self):
        return []


class StarsMatcher(object):
    """<STARS> indicates a chunk of text which is being skipped over"""
    def matches(self, xml):
        return xml.tag == 'STARS'

    def derive_nodes(self, xml):
        return [Node(label=[mtypes.STARS_TAG])]
