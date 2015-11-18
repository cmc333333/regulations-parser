from collections import defaultdict

from lxml import etree

from regparser.notice import changes
from regparser.notice.address import fetch_addresses
from regparser.notice.diff import parse_amdpar, find_section, find_subpart
from regparser.notice.diff import new_subpart_added
from regparser.notice.diff import DesignateAmendment
from regparser.notice.dates import fetch_dates
from regparser.notice.sxs import find_section_by_section
from regparser.notice.sxs import build_section_by_section
from regparser.notice.util import spaces_then_remove, swap_emphasis_tags
from regparser.notice.xml import fetch_cfr_parts, xmls_for_url
from regparser.tree.xml_parser import reg_text


def build_notice(cfr_title, cfr_part, fr_notice, fetch_xml=True,
                 xml_to_process=None):
    """Given JSON from the federal register, create our notice structure"""
    cfr_parts = set(str(ref['part']) for ref in fr_notice['cfr_references'])
    if cfr_part:
        cfr_parts.add(cfr_part)
    notice = {'cfr_title': cfr_title, 'cfr_parts': list(cfr_parts)}
    #   Copy over most fields
    for field in ['abstract', 'action', 'agency_names', 'comments_close_on',
                  'document_number', 'publication_date',
                  'regulation_id_numbers']:
        if fr_notice[field]:
            notice[field] = fr_notice[field]

    if fr_notice['effective_on']:
        notice['effective_on'] = fr_notice['effective_on']
        notice['initial_effective_on'] = fr_notice['effective_on']

    if fr_notice['html_url']:
        notice['fr_url'] = fr_notice['html_url']

    if fr_notice['citation']:
        notice['fr_citation'] = fr_notice['citation']

    notice['fr_volume'] = fr_notice['volume']
    notice['meta'] = {}
    for key in ('dates', 'end_page', 'start_page', 'type'):
        notice['meta'][key] = fr_notice[key]

    if xml_to_process is not None:
        return [process_xml(notice, xml_to_process)]
    elif fr_notice['full_text_xml_url'] and fetch_xml:
        xmls = xmls_for_url(fr_notice['full_text_xml_url'])
        notices = [process_xml(notice, xml) for xml in xmls]
        set_document_numbers(notices)
        return notices
    return [notice]


def split_doc_num(doc_num, effective_date):
    """ If we have a split notice, we construct a document number
    based on the original document number and the effective date. """
    effective_date = ''.join(effective_date.split('-'))
    return '%s_%s' % (doc_num, effective_date)


def set_document_numbers(notices):
    """If we have multiple notices (due to being split across multiple
    effective dates,) we need to fix their document numbers."""

    if len(notices) > 1:
        for notice in notices:
            notice['document_number'] = split_doc_num(
                notice['document_number'], notice['effective_on'])
    return notices


def process_designate_subpart(amendment):
    """ Process the designate amendment if it adds a subpart. """

    if 'Subpart' in amendment.destination:
        subpart_changes = {}

        for label in amendment.labels:
            label_id = '-'.join(label)
            subpart_changes[label_id] = {
                'action': 'DESIGNATE', 'destination': amendment.destination}
        return subpart_changes


def process_new_subpart(notice, amd_label, par):
    """ A new subpart has been added, create the notice changes. """
    subpart_changes = {}
    subpart_xml = find_subpart(par)
    subpart = reg_text.build_subpart(amd_label.label[0], subpart_xml)

    for change in changes.create_subpart_amendment(subpart):
        subpart_changes.update(change)
    return subpart_changes


def process_amendments(notice, notice_xml):
    """ Process the changes to the regulation that are expressed in the notice.
    """
    notice_changes = changes.NoticeChanges()

    default_cfr_part = notice['cfr_parts'][0]
    for parent in notice_xml.xpath('.//AMDPAR/..'):
        amdpars = parent.xpath('./AMDPAR')
        amended_labels = []
        designate_labels, other_labels = [], []
        context = [parent.get('PART') or default_cfr_part]
        for par in amdpars:
            als, context = parse_amdpar(par, context)
            amended_labels.extend(als)

        labels_by_part = defaultdict(list)
        for al in amended_labels:
            if isinstance(al, DesignateAmendment):
                subpart_changes = process_designate_subpart(al)
                if subpart_changes:
                    notice_changes.update(subpart_changes)
                designate_labels.append(al)
            elif new_subpart_added(al):
                notice_changes.update(process_new_subpart(notice, al, par))
                designate_labels.append(al)
            else:
                other_labels.append(al)
                labels_by_part[al.label[0]].append(al)

        notice_changes.create_xmlless_changes(other_labels)

        section_xml = find_section(par)
        for cfr_part, rel_labels in labels_by_part.iteritems():
            notice_changes.add_xml(section_xml, parent, cfr_part, rel_labels)

        notice_changes.amendments.extend(designate_labels)
        notice_changes.amendments.extend(other_labels)

        if other_labels:    # Carry cfr_part through amendments
            default_cfr_part = other_labels[-1].label[0]

    if notice_changes.amendments:
        notice['amendments'] = notice_changes.amendments
        notice['changes'] = notice_changes.changes

    return notice


def process_sxs(notice, notice_xml):
    """ Find and build SXS from the notice_xml. """
    sxs = find_section_by_section(notice_xml)
    # note we will continue to use cfr_parts[0] as the default SxS label until
    # we find a counter example
    sxs = build_section_by_section(sxs, notice['meta']['start_page'],
                                   notice['cfr_parts'][0])
    notice['section_by_section'] = sxs


def process_xml(notice, notice_xml):
    """Pull out relevant fields from the xml and add them to the notice"""
    notice = dict(notice)   # defensive copy

    xml_chunk = notice_xml.xpath('//FURINF/P')
    if xml_chunk:
        notice['contact'] = xml_chunk[0].text

    addresses = fetch_addresses(notice_xml)
    if addresses:
        notice['addresses'] = addresses

    if not notice.get('effective_on'):
        dates = fetch_dates(notice_xml)
        if dates and 'effective' in dates:
            notice['effective_on'] = dates['effective'][0]

    if not notice.get('cfr_parts'):
        cfr_parts = fetch_cfr_parts(notice_xml)
        notice['cfr_parts'] = cfr_parts

    process_sxs(notice, notice_xml)
    process_amendments(notice, notice_xml)
    add_footnotes(notice, notice_xml)

    return notice


def add_footnotes(notice, notice_xml):
    """ Parse the notice xml for footnotes and add them to the notice. """
    notice['footnotes'] = {}
    for child in notice_xml.xpath('//FTNT/*'):
        spaces_then_remove(child, 'PRTPAGE')
        swap_emphasis_tags(child)

        ref = child.xpath('.//SU')
        if ref:
            child.text = ref[0].tail
            child.remove(ref[0])
            content = child.text
            for cc in child:
                content += etree.tostring(cc)
            if child.tail:
                content += child.tail
            notice['footnotes'][ref[0].text] = content.strip()
