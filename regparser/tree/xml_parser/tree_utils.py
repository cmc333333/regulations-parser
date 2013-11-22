#vim: set encoding=utf-8
from itertools import chain
import re

import HTMLParser
from lxml import etree, objectify
from regparser.grammar.common import any_depth_p, any_p
from regparser.grammar.internal_citations import appendix_citation
from regparser.grammar.internal_citations import regtext_citation
from regparser.tree.paragraph import p_levels


def prepend_parts(parts_prefix, n):
    """ Recursively preprend parts_prefix to the parts of the node
    n. Parts is a list of markers that indicates where you are in the
    regulation text. """

    n.label = parts_prefix + n.label

    for c in n.children:
        prepend_parts(parts_prefix, c)
    return n


def unwind_stack(m_stack):
    """ Unwind the stack, collapsing sub-paragraphs that are on the stack into
    the children of the previous level. """
    children = m_stack.pop()
    parts_prefix = m_stack.peek_last()[1].label
    children = [prepend_parts(parts_prefix, c[1]) for c in children]
    m_stack.peek_last()[1].children = children


def add_to_stack(m_stack, node_level, node):
    """ Add a new node with level node_level to the stack. Unwind the stack
    when necessary. """
    last = m_stack.peek()
    element = (node_level, node)

    if node_level > last[0][0]:
        m_stack.push(element)
    elif node_level < last[0][0]:
        while last[0][0] > node_level:
            unwind_stack(m_stack)
            last = m_stack.peek()
        m_stack.push_last(element)
    else:
        m_stack.push_last(element)


def split_text(text, tokens):
    """
        Given a body of text that contains tokens,
        splice the text along those tokens.
    """
    starts = [text.find(t) for t in tokens]
    slices = zip(starts, starts[1:])
    texts = [text[i[0]:i[1]] for i in slices] + [text[starts[-1]:]]
    return texts


first_markers = [re.compile(ur'[\s|^|,|-|—]\((' + re.escape(level[0]) + ')\)')
                 for level in p_levels]


def get_collapsed_markers(text):
    """ We have collapsed markers that look something like this:
    (a) some text -(1) more text. We pull out -(1) type markers here. """
    exclude = [(start, end) for _, start, end in
               regtext_citation.scanString(text)]
    exclude += [(start, end) for _, start, end in
                appendix_citation.scanString(text)]

    matches = []
    for marker in first_markers:
        lst = [m for m in marker.finditer(text) if m.start() > 0]
        matches.extend([m for m in marker.finditer(text) if m.start() > 0])

        

    #   remove matches at the beginning
    start = text.find(')') + 1
    while matches and matches[0].start() == start:
        start = matches[0].end()
        matches = matches[1:]

    #   remove any that overlap with exclusions
    matches = [m for m in matches if not any(es <= m.start() and ee >= m.end()
               for es, ee in exclude)]
    #   get the letters
    return [match.group(1) for match in matches]


def get_paragraph_markers(text):
    """ From a body of text that contains paragraph markers, extract the
    markers. """
    for citation, start, end in any_depth_p.scanString(text):
        if start == 0:
            return citation[0][0]
    return []


def get_node_text(node):
    """ Extract all the text from an XML node (including the
    text of it's children). """
    parts = [node.text] +\
        list(chain(*([c.text, c.tail] for c in node.getchildren()))) +\
        [node.tail]
    return ''.join(filter(None, parts))


def get_node_text_tags_preserved(node):
    """ Given an XML node, generate text from the node, skipping the PRTPAGE
    tag. """

    html_parser = HTMLParser.HTMLParser()

    if node.text:
        node_text = node.text
    else:
        node_text = ''

    for c in node:
        if c.tag == 'E':
            #xlmns non-sense makes me do this.
            e_tag = '<E>%s</E>' % c.text
            node_text += e_tag
        if c.tail is not None:
            node_text += c.tail

    node_text = html_parser.unescape(node_text)
    return node_text
