from unittest import TestCase

from lxml import etree

from regparser.notice.util import *


class NoticeUtilTests(TestCase):
    def test_prepost_pend_spaces(self):
        for txt in ("a<em>bad</em>sentence", "a <em>bad</em>sentence",
                    "a<em>bad</em> sentence", "a <em>bad</em> sentence"):
            xml = etree.fromstring("<ROOT>This is " + txt + "</ROOT>")
            prepost_pend_spaces(xml.xpath("//em")[0])
            self.assertEqual(etree.tostring(xml),
                             '<ROOT>This is a <em>bad</em> sentence</ROOT>')

        xml = etree.fromstring(
            "<ROOT>"
            + "@<em>smith</em>: what<em>do</em>you think about $<em>15</em>"
            + "? That's <em>9</em>%!</ROOT>")
        for em in xml.xpath("//em"):
            prepost_pend_spaces(em)
        self.assertEqual(etree.tostring(xml),
                         '<ROOT>@<em>smith</em>: what <em>do</em> you think'
                         + " about $<em>15</em>? That's <em>9</em>%!</ROOT>")

    def test_spaces_then_remove_prtpage(self):
        for txt in ("Some<PRTPAGE />text", "Some <PRTPAGE />text",
                    "Some<PRTPAGE /> text"):
            xml = etree.fromstring("<ROOT>%s</ROOT>" % txt)
            xml = spaces_then_remove(xml, "PRTPAGE")
            self.assertEqual("Some text", xml.text)
