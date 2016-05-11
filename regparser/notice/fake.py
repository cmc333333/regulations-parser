"""Generate a minimal notice without hitting the FR"""
from regparser.notice.xml import NoticeXML, TitlePartsRef

from lxml import etree


def build(doc_number, effective_on, cfr_title, cfr_part):
<<<<<<< HEAD
    notice_xml = NoticeXML(etree.fromstring("""
        <ROOT>
            <PRTPAGE P="1" />
            <AGENCY></AGENCY>
            <SUBJECT></SUBJECT>
        </ROOT>
    """))
    notice_xml.fr_volume = 10
    notice_xml.version_id = doc_number
    notice_xml.effective = effective_on
    notice_xml.published = effective_on
    notice_xml.cfr_refs = [TitlePartsRef(cfr_title, [cfr_part])]
    return notice_xml


def effective_date_for(xml_tree):
    """Return the date associated with an annual edition of regulation XML"""
    nodes = xml_tree.xpath('//DATE') or xml_tree.xpath('//ORIGINALDATE')
    return nodes[0].text
=======
    return {
        "document_number": doc_number,
        "effective_on": effective_on,
        "initial_effective_on": effective_on,
        "publication_date": effective_on,
        "cfr_title": cfr_title,
        "cfr_parts": [str(cfr_part)],   # for consistency w/ normal notices
        "fr_url": None
    }
>>>>>>> 258f6c3a336b74e74e0c8fc82c48e44a29d37d13
