#vim: set encoding=utf-8
from unittest import TestCase

from regparser.grammar import unified


class GrammarCommonTests(TestCase):
    def test_depth1_p(self):
        text = '(c)(2)(ii)(A)(<E T="03">2</E>)'
        result = unified.depth1_p.parseString(text)
        self.assertEqual('c', result.p1)
        self.assertEqual('2', result.p2)
        self.assertEqual('ii', result.p3)
        self.assertEqual('A', result.p4)
        self.assertEqual('2', result.p5)

    def test_marker_subpart_title(self):
        text = u'Subpart A—Some Awesome Content'
        result = unified.marker_subpart_title.parseString(text)
        self.assertEqual('A', result.subpart)
        self.assertEqual('Some Awesome Content', result.subpart_title)

        text = u'Subpart B [Reserved]'
        result = unified.marker_subpart_title.parseString(text)
        self.assertEqual('B', result.subpart)
        self.assertEqual('[Reserved]', result.subpart_title)
