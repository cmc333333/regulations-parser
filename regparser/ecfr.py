"""Functions, etc. related to communicating and processing the eCFR bulk
export.
See http://www.ecfr.gov and https://www.gpo.gov/fdsys/bulkdata/ECFR/
"""
from datetime import date
from email.utils import parsedate
import logging
from time import strptime

from lxml import etree

from regparser.index.http_cache import http_client
from regparser.tree.reg_text import subjgrp_label
from regparser.tree.struct import Node
from regparser.tree.xml_parser import paragraph_processor, reg_text
from regparser.tree.xml_parser.flatsubtree_processor import FlatsubtreeMatcher
from regparser.tree.xml_parser.note_processor import NoteMatcher
from regparser.tree.xml_parser.xml_wrapper import root_property, XMLWrapper


ECFR_TITLE = (
    'https://www.gpo.gov/fdsys/bulkdata/ECFR/title-{cfr_title}/'
    'ECFR-title{cfr_title}.xml'
)
logger = logging.getLogger(__name__)


def xml_for_title(cfr_title):
    response = http_client().get(ECFR_TITLE.format(cfr_title=cfr_title))
    mod_tuple = parsedate(response.headers['last-modified'])
    xml = ECFRXML(etree.fromstring(response.content))
    xml.modified = date(*mod_tuple[:3])
    return xml


def title(xml_el):
    return xml_el.xpath('./HEAD')[0].text


def parse_sections(cfr_part, parent_xml):
    children = []
    for section_xml in parent_xml.xpath('./DIV8'):
        section_num = section_xml.attrib['N'].split('.')[-1]
        node = Node(label=[cfr_part, section_num], title=title(section_xml))
        children.append(ECFRSectionProcessor().process(section_xml, node))
    return children


def parse_sub_parts_and_groups(cfr_part, part_xml):
    result = []

    empty_part_sections = part_xml.xpath('./DIV8')
    if empty_part_sections:
        result.append(Node(
            label=[cfr_part, 'Subpart'], node_type=Node.EMPTYPART,
            children=parse_sections(cfr_part, part_xml)
        ))

    subject_group_letters = []
    for sub in part_xml.xpath('./DIV6|./DIV7'):
        if sub.tag == 'DIV6':   # Subpart
            label = [cfr_part, 'Subpart', sub.attrib['N']]
        else:
            short = subjgrp_label(title(sub), subject_group_letters)
            subject_group_letters.append(short)
            label = [cfr_part, 'Subgrp', short]
        result.append(Node(
            label=label, title=title(sub), node_type=Node.SUBPART,
            children=parse_sections(cfr_part, sub)
        ))
    return result


class ECFRXML(XMLWrapper):
    modified = root_property(
        'modified', lambda v: date(*strptime(v, '%Y-%m-%d')[:3]))

    def cfr_parts(self):
        parts = []
        for div in self.xpath('.//DIV5'):
            parts.append(div.attrib['N'])
        return parts

    def parse_part(self, cfr_part):
        part_xmls = self.xpath('.//DIV5[@N={}]'.format(cfr_part))
        if not part_xmls:
            logger.warning('No XML for cfr_part %s', cfr_part)
            return None
        part_xml = part_xmls[0]
        return Node(label=[cfr_part], title=title(part_xml),
                    children=parse_sub_parts_and_groups(cfr_part, part_xml))


class ECFRSectionProcessor(paragraph_processor.ParagraphProcessor):
    MATCHERS = [
        reg_text.ParagraphMatcher(),
        FlatsubtreeMatcher(tags=['EXTRACT'], node_type=Node.EXTRACT),
        NoteMatcher(),
        paragraph_processor.IgnoreTagMatcher(
            'APPRO', 'CITA', 'HEAD', 'SECAUTH')
    ]
