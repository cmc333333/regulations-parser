""" This module contains functions to help parse the changes in a notice.
Changes are the exact details of how the pargraphs, sections etc. in a
regulation have changed.  """
import copy
from collections import defaultdict

from lxml import etree

from regparser.grammar.tokens import Verb
from regparser.layer.paragraph_markers import marker_of
from regparser.notice.amdpars import (
    Amendment, DesignateAmendment, fix_section_node, new_subpart_added,
    parse_amdpar)
from regparser.notice.build_appendix import parse_appendix_changes
from regparser.notice.build_interp import parse_interp_changes
from regparser.tree import struct
from regparser.tree.paragraph import p_levels
from regparser.tree.xml_parser.reg_text import (
    build_from_section, build_subpart)


def bad_label(node):
    """ Look through a node label, and return True if it's a badly formed
    label. We can do this because we know what type of character should up at
    what point in the label. """

    if node.node_type == struct.Node.REGTEXT:
        for i, l in enumerate(node.label):
            if i == 0 and not l.isdigit():
                return True
            elif i == 1 and not l.isdigit():
                return True
            elif i > 1 and l not in p_levels[i-2]:
                return True
    return False


def impossible_label(n, amendments):
    """ Return True if n is not in the same family as amended_labels. """
    for amendment in amendments:
        if n.label_id().startswith(amendment.label_id()):
            return False
    return True


def find_candidate(root, label_last):
    """
        Look through the tree for a node that has the same paragraph marker as
        the one we're looking for (and also has no children).  That might be a
        mis-parsed node. Because we're parsing partial sections in the notices,
        it's likely we might not be able to disambiguate between paragraph
        markers.
    """
    def check(node):
        """ Match last part of label."""
        if node.label and node.label[-1] == label_last:
            return node

    candidates = struct.walk(root, check)
    if len(candidates) > 1:
        # Look for mal-formed labels, labels that can't exist (because we're
        # not amending that part of the reg, or eventually a parent with no
        # children.

        bad_labels = [n for n in candidates if bad_label(n)]
        impossible_labels = [n for n in candidates
                             if hasattr(n, 'obviously_misparsed')]
        no_children = [n for n in candidates if n.children == []]

        # If we have a single option in any of the categories, return that.
        if len(bad_labels) == 1:
            return bad_labels
        elif len(impossible_labels) == 1:
            return impossible_labels
        elif len(no_children) == 1:
            return no_children
    return candidates


def find_misparsed_node(tree, label):
    """ Nodes can get misparsed in the sense that we don't always know where
    they are in the tree or have their correct label. The first part
    corrects markerless labeled nodes by updating the node's label if
    the source text has been changed to include the markerless paragraph
    (ex. 123-44-p6 for paragraph 6). we know this because `label` here
    is parsed from that change. The second part uses label to find a
    candidate for a mis-parsed node and creates an appropriate change. """

    is_markerless = struct.Node.is_markerless_label(label)
    markerless_paragraphs = struct.filter_walk(
        tree,
        struct.Node.is_markerless_label)
    if is_markerless and len(markerless_paragraphs) == 1:
        markerless_paragraphs[0].label = label
        return markerless_paragraphs[0]

    candidates = find_candidate(tree, label[-1])
    if len(candidates) == 1:
        candidates[0].label = label
        return candidates[0]


def format_node(node, amendment):
    """ Format a node and add in amendment information. """
    # Copy the node, remove it's children, and dump its XML to string
    node_no_kids = copy.deepcopy(node)
    node_no_kids.children = []

    try:
        node_no_kids.source_xml = etree.tostring(node_no_kids.source_xml)
    except TypeError:
        # source_xml wasn't serializable
        pass

    node_as_dict = {
        'node': node_no_kids,
        'action': amendment.action
    }

    if amendment.field:
        node_as_dict['field'] = amendment.field
    return {node.label_id(): node_as_dict}


def create_add_amendment(amendment, amd_node):
    """ An amendment comes in with a whole tree structure. We break apart the
    tree here (this is what flatten does), convert the Node objects to JSON
    representations. This ensures that each amendment only acts on one node.
    In addition, this futzes with the change's field when stars are present.
    """

    nodes_list = []
    flatten_tree(nodes_list, amd_node)
    changes = [{n.label_id(): {'node': n, 'action': amendment.action}}
               for n in nodes_list]

    for change in filter(lambda c: c.values()[0]['action'] == 'PUT', changes):
        label = change.keys()[0]
        node = struct.find(amd_node, label)
        text = node.text.strip()
        marker = marker_of(node)
        text = text[len(marker):].strip()
        # Text is stars, but this is not the root. Explicitly try to keep
        # this node
        if text == '* * *':
            change[label]['action'] = Verb.KEEP

        # If text ends with a colon and is followed by stars, assume we are
        # only modifying the intro text
        if (text[-1:] == ':' and node.label == amd_node.label
                and node.source_xml is not None):
            following = node.source_xml.getnext()
            if following is not None and following.tag == 'STARS':
                change[label]['field'] = '[text]'

    return changes


def create_subpart_amendment(subpart_node):
    """ Create an amendment that describes a subpart. In particular
    when the list of nodes added gets flattened, each node specifies which
    subpart it's part of. """
    changes = create_add_amendment(Amendment('POST', subpart_node.label_id()),
                                   subpart_node)
    for change in changes:
        for c in change.values():
            c['extras'] = {'subpart': subpart_node.label}
    return changes


def flatten_tree(node_list, node):
    """ Flatten a tree, removing all hierarchical information, making a
    list out of all the nodes. """
    for c in node.children:
        flatten_tree(node_list, c)

    # Don't be destructive.
    no_kids = copy.deepcopy(node)
    no_kids.children = []
    node_list.append(no_kids)


def remove_intro(l):
    """ Remove the marker that indicates this is a change to introductory
    text. """
    return l.replace('[text]', '')


def pretty_change(change):
    """Pretty print output for a change"""
    node = change.get('node')
    field = change.get('field')
    if change['action'] == Verb.PUT and field:
        return '%s changed to: %s' % (field.strip('[]').title(),
                                      node.title or node.text)
    elif change['action'] in (Verb.PUT, Verb.POST):
        verb = 'Modified' if change['action'] == Verb.PUT else 'Added'
        if node.title:
            return verb + ' (title: %s): %s' % (node.title, node.text)
        else:
            return verb + ": " + node.text
    elif change['action'] == Verb.DELETE:
        return 'Deleted'
    elif change['action'] == Verb.DESIGNATE:
        return 'Moved to ' + '-'.join(change['destination'])
    elif change['action'] == Verb.RESERVE:
        return 'Reserved'
    elif change['action'] == Verb.KEEP:
        return 'Mentioned but not modified'
    else:
        return change['action']


def process_designate_subpart(amendment):
    """ Process the designate amendment if it adds a subpart. """

    if 'Subpart' in amendment.destination:
        subpart_changes = {}

        for label in amendment.labels:
            label_id = '-'.join(label)
            subpart_changes[label_id] = {
                'action': 'DESIGNATE', 'destination': amendment.destination}
        return subpart_changes


def process_new_subpart(amd_label, parent):
    """ A new subpart has been added, create the notice changes. """
    subpart_changes = {}
    subpart_xml = parent.xpath('./SUBPART')[0]
    subpart = build_subpart(amd_label.label[0], subpart_xml)

    for change in create_subpart_amendment(subpart):
        subpart_changes.update(change)
    return subpart_changes


def find_trees(xml_parent, cfr_parts, amendments):
    """Find and parse regtext sections, interpretations, appendices"""
    section_xmls = xml_parent.xpath('./SECTION')
    if not section_xmls:
        last_amdpar = xml_parent.xpath('./AMDPAR')[-1]
        paragraphs = [s for s in last_amdpar.itersiblings() if s.tag == 'P']
        if len(paragraphs) > 0:
            potential_section = fix_section_node(paragraphs, last_amdpar)
            if potential_section:
                section_xmls.append(potential_section)

    for cfr_part in cfr_parts:
        for section_xml in section_xmls:
            for section in build_from_section(cfr_part, section_xml):
                yield section
        for appendix in parse_appendix_changes(amendments, cfr_part,
                                               xml_parent):
            yield appendix
        interp = parse_interp_changes(amendments, cfr_part, xml_parent)
        if interp:
            yield interp


def find_node_for_amendment(amendment, root, node_lookup):
    if not isinstance(amendment, DesignateAmendment):
        label_id = amendment.label_id()
        if label_id in node_lookup:
            return node_lookup[label_id]
        elif amendment.action in ('POST', 'PUT', 'RESERVE'):
            return find_misparsed_node(root, amendment.label)


class NoticeChanges(object):
    """ Notice changes. """
    def __init__(self, initial_cfr_part=None):
        self.default_cfr_part = initial_cfr_part
        self.changes = defaultdict(list)
        self.amendments = []

    def update(self, changes):
        """ Essentially add more changes into NoticeChanges. This is
        cognizant of the fact that a single label can have more than
        one change. Do not add the same change twice (as may occur if both
        the parent and child are marked as added)"""
        for l, c in changes.items():
            if c not in self.changes[l]:
                self.changes[l].append(c)

    def find_amendments(self, amdpar_parent):
        amdpars = amdpar_parent.xpath('./AMDPAR')
        amendments = []
        context = [amdpar_parent.get('PART') or self.default_cfr_part]
        for par in amdpars:
            amends, context = parse_amdpar(par, context)
            for al in amends:
                amendments.append(al)
        return amendments

    def process_amendment(self, amendment, parent, node):
        if isinstance(amendment, DesignateAmendment):
            subpart_changes = process_designate_subpart(amendment)
            if subpart_changes:
                self.update(subpart_changes)
        elif new_subpart_added(amendment):
            self.update(process_new_subpart(amendment, parent))
        elif amendment.action == 'DELETE':
            self.update({amendment.label_id(): {'action': 'DELETE'}})
            self.default_cfr_part = amendment.label[0]
        elif amendment.action == 'MOVE':
            destination = [d for d in amendment.destination if d != '?']
            self.update({amendment.label_id(): {
                'action': 'MOVE', 'destination': destination}})
            self.default_cfr_part = amendment.label[0]
        elif node and amendment.action == 'RESERVE':
            node_no_kids = copy.deepcopy(node)
            node_no_kids.children = []
            self.update({amendment.label_id(): {
                'action': 'RESERVE', 'node': node_no_kids}})
        elif node and amendment.action in ('POST', 'PUT') and amendment.field:
            self.update(format_node(node, amendment))
        elif node and amendment.action in ('POST', 'PUT'):
            for result in create_add_amendment(amendment, node):
                self.update(result)
        elif not node:
            print "ERRRRRROR"
        else:
            print 'NOT HANDLED: %s' % amendment['action']

    def process_amdpars(self, notice_xml):
        for parent in notice_xml.xpath('.//AMDPAR/..'):
            amendments = self.find_amendments(parent)
            cfr_parts = set(a.label[0] for a in amendments
                            if hasattr(a, 'label'))
            node_lookup, root = {}, struct.Node()
            for tree in find_trees(parent, cfr_parts, amendments):
                root.children.append(tree)
                for node in struct.walk(tree, lambda n: n):
                    node.child_labels = [c.label_id() for c in node.children]
                    node_lookup[node.label_id()] = node
                    if impossible_label(node, amendments):
                        node.obviously_misparsed = True

            for amendment in amendments:
                node = find_node_for_amendment(amendment, root, node_lookup)
                self.process_amendment(amendment, parent, node)
                self.amendments.append(amendment)
                if not isinstance(amendment, DesignateAmendment):
                    self.default_cfr_part = amendment.label[0]
