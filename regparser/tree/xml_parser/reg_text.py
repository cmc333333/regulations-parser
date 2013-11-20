#!/usr/bin/env python
import re
from lxml import etree
from regparser.tree.struct import Node
from regparser.tree.paragraph import p_levels
from regparser.tree.node_stack import NodeStack
from regparser.tree.xml_parser.appendices import build_non_reg_text
from regparser.tree import reg_text
from regparser.tree.xml_parser import tree_utils


def determine_level(c, current_level, next_marker=None):
    """ Regulation paragraphs are hierarchical. This determines which level
    the paragraph is at. Convert between p_level indexing and depth here by
    adding one"""
    potential = [i for i in range(len(p_levels)) if c in p_levels[i]]
    #   We want to account for later levels (e.g. roman numerals) first
    potential = list(reversed(potential))

    if len(potential) > 1 and next_marker:     # ambiguity
        following = [i for i in range(len(p_levels))
                     if next_marker in p_levels[i]]
        following = list(reversed(following))

        #   Add character index
        potential = [(level, p_levels[level].index(c)) for level in potential]
        following = [(level, p_levels[level].index(next_marker))
                     for level in following]

        #   Check if we can be certain using the following marker
        for pot_level, pot_idx in potential:
            for next_level, next_idx in following:
                if (    #   E.g. i followed by A or i followed by 1
                    (next_idx == 0 and next_level == pot_level + 1)
                    or  #   E.g. i followed by ii
                    (next_level == pot_level and next_idx == pot_idx + 1)
                    or  #   E.g. i followed by 3
                    (next_level < pot_level and next_idx > 0)):
                    return pot_level + 1
        print "Couldn't figure out:"
        print potential
        print following
        

    return potential[0] + 1


def get_reg_part(reg_doc):
    """
    The CFR Part number for a regulation is contained within
    an EAR tag, for a Federal Register notice it's in a REGTEXT tag. Get the
    part number of the regulation.
    """

    #FR notice
    reg_text_xml = reg_doc.xpath('//REGTEXT')
    if reg_text_xml:
        return reg_text_xml[0].attrib['PART']

    #e-CFR XML
    reg_ear = reg_doc.xpath('//PART/EAR')
    if reg_ear:
        return reg_ear[0].text.split('Pt.')[1].strip()


def get_title(reg_doc):
    """ Extract the title of the regulation. """
    parent = reg_doc.xpath('//PART/HD')[0]
    title = parent.text
    return title


def build_tree(reg_xml):
    doc = etree.fromstring(reg_xml)

    reg_part = get_reg_part(doc)
    title = get_title(doc)

    tree = Node("", [], [reg_part], title)

    part = doc.xpath('//PART')[0]

    subpart_xmls = [c for c in part.getchildren() if c.tag == 'SUBPART']
    if len(subpart_xmls) > 0:
        subparts = [build_subpart(reg_part, s) for s in subpart_xmls]
        tree.children = subparts
    else:
        section_xmls = [c for c in part.getchildren() if c.tag == 'SECTION']
        sections = [build_section(reg_part, s) for s in section_xmls]
        empty_part = reg_text.build_empty_part(reg_part)
        empty_part.children = sections
        tree.children = [empty_part]

    return tree


def get_subpart_title(subpart_xml):
    hds = subpart_xml.xpath('./HD')
    return [hd.text for hd in hds][0]


def build_subpart(reg_part, subpart_xml):
    subpart_title = get_subpart_title(subpart_xml)
    subpart = reg_text.build_subpart(subpart_title, reg_part)

    sections = []
    for ch in subpart_xml.getchildren():
        if ch.tag == 'SECTION':
            sections.append(build_section(reg_part, ch))

    subpart.children = sections
    return subpart


def get_markers(text):
    """ Extract all the paragraph markers from text  """
    markers = tree_utils.get_paragraph_markers(text)
    collapsed_markers = tree_utils.get_collapsed_markers(text)
    markers_list = [m for m in markers] + [m for m in collapsed_markers]
    return markers_list


def get_markers_and_text(node, markers_list):
    node_text = tree_utils.get_node_text(node)
    text_with_tags = tree_utils.get_node_text_tags_preserved(node)

    if len(markers_list) > 1:
        actual_markers = ['(%s)' % m for m in markers_list]
        node_texts = tree_utils.split_text(node_text, actual_markers)
        tagged_texts = tree_utils.split_text(text_with_tags, actual_markers)
        node_text_list = zip(node_texts, tagged_texts)
    elif markers_list:
        node_text_list = [(node_text, text_with_tags)]
    return zip(markers_list, node_text_list)


def build_section(reg_part, section_xml):
    p_level = 1
    m_stack = NodeStack()
    section_texts = []
    for ch in section_xml.getchildren():
        if ch.tag == 'P':
            text = ' '.join([ch.text] + [c.tail for c in ch if c.tail])
            markers_list = get_markers(text)

            if not markers_list:
                node_text = tree_utils.get_node_text(ch)
                tagged_text = tree_utils.get_node_text_tags_preserved(ch)
                section_texts.append((node_text, tagged_text))
            else:
                markers_and_text = get_markers_and_text(ch, markers_list)

                for idx, pair in enumerate(markers_and_text):
                    m, node_text = pair
                    n = Node(node_text[0], [], [str(m)])
                    n.tagged_text = unicode(node_text[1])

                    print text
                    sib = ch.getnext()
                    if idx < len(markers_and_text) - 1:
                        new_p_level = determine_level(m, p_level,
                                                      markers_list[idx+1])
                    elif sib is not None:
                        next_text = ' '.join([sib.text]
                                             + [s.tail for s in sib if s.tail])
                        next_markers = get_markers(next_text)
                        if next_markers:
                            new_p_level = determine_level(m, p_level,
                                                          next_markers[0])
                        else:
                            new_p_level = determine_level(m, p_level)
                    else:
                        new_p_level = determine_level(m, p_level)
                    last = m_stack.peek()
                    if len(last) == 0:
                        m_stack.push_last((new_p_level, n))
                    else:
                        tree_utils.add_to_stack(m_stack, new_p_level, n)
                    p_level = new_p_level

    section_title = section_xml.xpath('SECTNO')[0].text
    subject_text_xml = section_xml.xpath('SUBJECT')
    if not subject_text_xml:
        subject_text_xml = section_xml.xpath('RESERVED')
    subject_text = subject_text_xml[0].text
    if subject_text:
        section_title += " " + subject_text

    section_number_match = re.search(r'%s\.(\d+)' % reg_part, section_title)
    #   Sometimes not reg text sections get mixed in
    if section_number_match:
        section_number = section_number_match.group(1)

        plain_sect_texts = [s[0] for s in section_texts]
        tagged_sect_texts = [s[1] for s in section_texts]

        section_text = ' '.join([section_xml.text] + plain_sect_texts)
        tagged_section_text = ' '.join([section_xml.text] + tagged_sect_texts)
        sect_node = Node(
            section_text, label=[reg_part, section_number],
            title=section_title)
        sect_node.tagged_text = tagged_section_text

        m_stack.add_to_bottom((1, sect_node))

        while m_stack.size() > 1:
            tree_utils.unwind_stack(m_stack)

        return m_stack.pop()[0][1]
