# vim: set encoding=utf-8
from unittest import TestCase

from lxml import etree

from regparser.notice import changes
from regparser.tree.struct import Node, find
from regparser.notice.amdpars import Amendment, DesignateAmendment
from tests.xml_builder import XMLBuilderMixin


class ChangesTests(XMLBuilderMixin, TestCase):
    def build_tree(self):
        n1 = Node('n1', label=['200', '1'])
        n2 = Node('n1i', label=['200', 1, 'i'])
        n3 = Node('n2', label=['200', '2'])
        n4 = Node('n3', label=['200', '3'])
        n5 = Node('n3a', label=['200', '3', 'a'])

        n1.children = [n2]
        n4.children = [n5]
        root = Node('root', label=['200'], children=[n1, n3, n4])
        return root

    def test_find_candidate(self):
        root = self.build_tree()
        result = changes.find_candidate(root, 'i')[0]
        self.assertEqual(u'n1i', result.text)

        n2c = Node('n3c', label=['200', '2', 'i', 'i'])
        n2 = find(root, '200-2')
        n2.children = [n2c]

        result = changes.find_candidate(root, 'i')[0]
        self.assertEqual(result.label, ['200', '2', 'i', 'i'])

    def test_not_find_candidate(self):
        root = self.build_tree()
        result = changes.find_candidate(root, 'j')
        self.assertEqual(result, [])

    def test_find_candidate_impossible_label(self):
        n1 = Node('', label=['200', '1'])
        n1a = Node('', label=['200', '1', 'a'])

        n1a1i = Node('', label=['200', '1', 'a', '1', 'i'])
        n1a.children = [n1a1i]

        n1b = Node('', label=['200', '1', 'b'])
        n1i = Node('', label=['200', '1', 'i'])
        n1i.obviously_misparsed = True
        n1.children = [n1a, n1b, n1i]

        root = Node('root', label=['200'], children=[n1])
        candidate = changes.find_candidate(root, 'i')[0]

        self.assertEqual(candidate.label, ['200', '1', 'i'])

    def test_create_add_amendment(self):
        root = self.build_tree()

        amendments = changes.create_add_amendment(
            Amendment('POST', root.label_id()), root)
        self.assertEqual(6, len(amendments))

        amends = {}
        for a in amendments:
            amends.update(a)

        for l in ['200-1-i', '200-1', '200-2', '200-3-a', '200-3', '200']:
            self.assertTrue(l in amends)

        for label, node in amends.items():
            self.assertEqual(label, '-'.join(node['node'].label))
            self.assertEqual(node['action'], 'POST')

    def test_flatten_tree(self):
        tree = self.build_tree()

        node_list = []
        changes.flatten_tree(node_list, tree)

        self.assertEqual(6, len(node_list))
        for n in node_list:
            self.assertEqual(n.children, [])

    def test_remove_intro(self):
        text = 'abcd[text]'
        self.assertEqual('abcd', changes.remove_intro(text))

    def test_resolve_candidates(self):
        root = Node(label=['200'], children=[
            Node('n1', label=['200', '1']),
            Node('n2', label=['200', '1', 'i'])
        ])
        self.assertEqual(
            changes.find_misparsed_node(root, ['200', '1', 'a', 'i']),
            Node('n2', label=['200', '1', 'a', 'i']))

    def test_resolve_candidates_double_delete(self):
        """In the unfortunate case where *two* candidates are wrong make
        sure we don't blow up"""
        root = Node(label=['200'], children=[
            Node('n1', label=['200', '1', 'i']),
            Node('n2', label=['200', '1', 'i'])
        ])
        self.assertIsNone(changes.find_misparsed_node(
            root, ['200', '1', 'a', 'i']))

    def test_match_labels_and_changes_move(self):
        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(
            Amendment('MOVE', '200-1', '200-2'), None, None)
        self.assertEqual(notice_changes.changes, {
            '200-1': [{'action': 'MOVE', 'destination': ['200', '2']}]})

    def test_match_labels_and_changes_delete(self):
        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(
            Amendment('DELETE', '200-1-a-i'), None, None)
        self.assertEqual(notice_changes.changes, {
            '200-1-a-i': [{'action': 'DELETE'}]})

    def test_match_labels_and_changes_reserve(self):
        node = Node('a-node', label=['200', '2', 'a'])
        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(
            Amendment('RESERVE', '200-2-a'), None, node)
        self.assertEqual(notice_changes.changes['200-2-a'][0]['action'],
                         'RESERVE')
        self.assertEqual(notice_changes.changes['200-2-a'][0]['node'], node)

    def section_node(self):
        n1 = Node('n2', label=['200', '2'])
        n2 = Node('n2a', label=['200', '2', 'a'])

        n1.children = [n2]
        root = Node('root', label=['200'], children=[n1])
        return root

    def test_match_labels_and_changes(self):
        n2 = Node('n2', label=['200', '2'])
        n2a = Node('n2a', label=['200', '2', 'a'])
        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(Amendment('POST', '200-2'), None, n2)
        notice_changes.process_amendment(
            Amendment('PUT', '200-2-a'), None, n2a)

        self.assertEqual(notice_changes.changes['200-2'],
                         [{'action': 'POST', 'node': n2}])
        self.assertEqual(notice_changes.changes['200-2-a'],
                         [{'action': 'PUT', 'node': n2a}])

    def test_bad_label(self):
        label = ['205', '4', 'a', '1', 'ii', 'A']
        node = Node('text', label=label, node_type=Node.REGTEXT)
        self.assertFalse(changes.bad_label(node))

        node.label = ['205', '38', 'i', 'vii', 'A']
        self.assertTrue(changes.bad_label(node))

        node.label = ['205', 'ii']
        self.assertTrue(changes.bad_label(node))

        node.label = ['205', '38', 'A', 'vii', 'A']
        self.assertTrue(changes.bad_label(node))

    def test_impossible_label(self):
        amendments = [Amendment('POST', '205-35-c-1'),
                      Amendment('POST', '205-35-c-2')]
        node = Node('', label=['205', '35', 'v'])
        self.assertTrue(changes.impossible_label(node, amendments))

        node = Node('', label=['205', '35', 'c', '1', 'i'])
        self.assertFalse(changes.impossible_label(node, amendments))

    def test_pretty_changes(self):
        """Verify the output for a variety of "changes" """
        self.assertEqual(
            changes.pretty_change({'action': 'DELETE'}), 'Deleted')
        self.assertEqual(
            changes.pretty_change({'action': 'RESERVE'}), 'Reserved')
        self.assertEqual(
            changes.pretty_change({'action': 'KEEP'}),
            'Mentioned but not modified')
        self.assertEqual(
            changes.pretty_change({'action': 'DESIGNATE',
                                   'destination': ['123', '43', 'a', '2']}),
            'Moved to 123-43-a-2')

        node = Node('Some Text')
        change = {'action': 'PUT', 'node': node}
        self.assertEqual(
            changes.pretty_change(change), 'Modified: Some Text')

        change['action'] = 'POST'
        self.assertEqual(
            changes.pretty_change(change), 'Added: Some Text')

        node.title = 'A Title'
        self.assertEqual(
            changes.pretty_change(change), 'Added (title: A Title): Some Text')

        change['action'] = 'PUT'
        self.assertEqual(
            changes.pretty_change(change),
            'Modified (title: A Title): Some Text')

        change['field'] = '[title]'
        self.assertEqual(
            changes.pretty_change(change), 'Title changed to: A Title')

        node.title = None
        change['field'] = '[a field]'
        self.assertEqual(
            changes.pretty_change(change), 'A Field changed to: Some Text')

    def test_process_designate_subpart(self):
        p_list = ['200-?-1-a', '200-?-1-b']
        destination = '205-Subpart:A'
        amended_label = DesignateAmendment('DESIGNATE', p_list, destination)

        subpart_changes = changes.process_designate_subpart(amended_label)

        self.assertEqual(['200-1-a', '200-1-b'], subpart_changes.keys())

        for p, change in subpart_changes.items():
            self.assertEqual(change['destination'], ['205', 'Subpart', 'A'])
            self.assertEqual(change['action'], 'DESIGNATE')

    def new_subpart_xml(self):
        with self.tree.builder("RULE") as rule:
            with rule.REGTEXT(PART="105", TITLE="12") as regtext:
                regtext.AMDPAR(u"3. In § 105.1, revise paragraph (b) to read "
                               "as follows:")
                with regtext.SECTION() as section:
                    section.SECTNO(u"§ 105.1")
                    section.SUBJECT("Purpose.")
                    section.STARS()
                    section.P("(b) This part carries out.")
            with rule.REGTEXT(PART="105", TITLE="12") as regtext:
                regtext.AMDPAR("6. Add subpart B to read as follows:")
                with regtext.CONTENTS() as contents:
                    with contents.SUBPART() as subpart:
                        subpart.SECHD("Sec.")
                        subpart.SECTNO("105.30")
                        subpart.SUBJECT("First In New Subpart.")
                with regtext.SUBPART() as subpart:
                    subpart.HD(u"Subpart B—Requirements", SOURCE="HED")
                    with subpart.SECTION() as section:
                        section.SECTNO("105.30")
                        section.SUBJECT("First In New Subpart")
                        section.P("For purposes of this subpart, the follow "
                                  "apply:")
                        section.P('(a) "Agent" means agent.')
        return self.tree.render_xml()

    def test_process_new_subpart(self):
        amended_label = Amendment('POST', '105-Subpart:B')
        subpart_changes = changes.process_new_subpart(
            amended_label, self.new_subpart_xml().xpath('.//REGTEXT')[1])

        new_nodes_added = ['105-Subpart-B', '105-30', '105-30-a']
        self.assertEqual(new_nodes_added, subpart_changes.keys())

        for l, n in subpart_changes.items():
            self.assertEqual(n['action'], 'POST')

        self.assertEqual(
            subpart_changes['105-Subpart-B']['node'].node_type, 'subpart')


class NoticeChangesTests(TestCase):
    def test_update_duplicates(self):
        nc = changes.NoticeChanges()
        nc.update({'123-12': {'action': 'DELETE'},
                   '123-22': {'action': 'OTHER'}})
        nc.update({'123-12': {'action': 'DELETE'}})
        nc.update({'123-12': {'action': 'OTHER'}})
        nc.update({'123-22': {'action': 'OTHER'},
                   '123-32': {'action': 'LAST'}})

        self.assertTrue('123-12' in nc.changes)
        self.assertTrue('123-22' in nc.changes)
        self.assertTrue('123-32' in nc.changes)

        self.assertEqual(nc.changes['123-12'],
                         [{'action': 'DELETE'}, {'action': 'OTHER'}])
        self.assertEqual(nc.changes['123-22'], [{'action': 'OTHER'}])
        self.assertEqual(nc.changes['123-32'], [{'action': 'LAST'}])

    def test_create_xml_changes_reserve(self):
        n2a = Node('[Reserved]', label=['200', '2', 'a'])

        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(
            Amendment('RESERVE', '200-2-a'), None, n2a)

        reserve = notice_changes.changes['200-2-a'][0]
        self.assertEqual(reserve['action'], 'RESERVE')
        self.assertEqual(reserve['node'].text, u'[Reserved]')

    def test_create_xml_changes_stars(self):
        n2a1 = Node('(1) Content', label=['200', '2', 'a', '1'])
        n2a2 = Node('(2) Content', label=['200', '2', 'a', '2'])
        n2a = Node('(a) * * *', label=['200', '2', 'a'], children=[n2a1, n2a2])

        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(
            Amendment('PUT', '200-2-a'), None, n2a)

        for label in ('200-2-a-1', '200-2-a-2'):
            self.assertTrue(label in notice_changes.changes)
            self.assertEqual(1, len(notice_changes.changes[label]))
            change = notice_changes.changes[label][0]
            self.assertEqual('PUT', change['action'])
            self.assertFalse('field' in change)

        self.assertTrue('200-2-a' in notice_changes.changes)
        self.assertEqual(1, len(notice_changes.changes['200-2-a']))
        change = notice_changes.changes['200-2-a'][0]
        self.assertEqual('KEEP', change['action'])
        self.assertFalse('field' in change)

    def test_create_xml_changes_stars_hole(self):
        n2a1 = Node('(1) * * *', label=['200', '2', 'a', '1'])
        n2a2 = Node('(2) a2a2a2', label=['200', '2', 'a', '2'])
        n2a = Node('(a) aaa', label=['200', '2', 'a'], children=[n2a1, n2a2])

        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(
            Amendment('PUT', '200-2-a'), None, n2a)

        for label in ('200-2-a', '200-2-a-2'):
            self.assertTrue(label in notice_changes.changes)
            self.assertEqual(1, len(notice_changes.changes[label]))
            change = notice_changes.changes[label][0]
            self.assertEqual('PUT', change['action'])
            self.assertFalse('field' in change)

        self.assertTrue('200-2-a-1' in notice_changes.changes)
        self.assertEqual(1, len(notice_changes.changes['200-2-a-1']))
        change = notice_changes.changes['200-2-a-1'][0]
        self.assertEqual('KEEP', change['action'])
        self.assertFalse('field' in change)

    def test_create_xml_changes_child_stars(self):
        xml = etree.fromstring("<ROOT><P>(a) Content</P><STARS /></ROOT>")
        n2a = Node('(a) Content', label=['200', '2', 'a'],
                   source_xml=xml.xpath('//P')[0])

        amendment = Amendment('PUT', '200-2-a')
        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(amendment, None, n2a)

        self.assertTrue('200-2-a' in notice_changes.changes)
        self.assertTrue(1, len(notice_changes.changes['200-2-a']))
        change = notice_changes.changes['200-2-a'][0]
        self.assertEqual('PUT', change['action'])
        self.assertFalse('field' in change)

        n2a.text = n2a.text + ":"
        n2a.source_xml.text = n2a.source_xml.text + ":"

        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(amendment, None, n2a)

        self.assertTrue('200-2-a' in notice_changes.changes)
        self.assertTrue(1, len(notice_changes.changes['200-2-a']))
        change = notice_changes.changes['200-2-a'][0]
        self.assertEqual('PUT', change['action'])
        self.assertEqual('[text]', change.get('field'))

    def test_create_xmlless_changes(self):
        notice_changes = changes.NoticeChanges()
        notice_changes.process_amendment(
            Amendment('DELETE', '200-2-a'), None, None)
        self.assertEqual({'action': 'DELETE'},
                         notice_changes.changes['200-2-a'][0])

        notice_changes.process_amendment(
            Amendment('MOVE', '200-2-b', '200-2-c'), None, None)
        self.assertEqual({'action': 'MOVE', 'destination': ['200', '2', 'c']},
                         notice_changes.changes['200-2-b'][0])
