from unittest import TestCase

from click.testing import CliRunner

from regparser.commands import fill_with_rules
from regparser.index import dependency, entry
from regparser.tree.struct import Node


class CommandsFillWithRulesTests(TestCase):
    def setUp(self):
        self.cli = CliRunner()

    def test_dependencies(self):
        """Expect nonexistent trees to depend on their predecessor, associated
        rule changes and version files. Shouldn't add dependencies for the
        first version, if missing"""
        with self.cli.isolated_filesystem():
            version_ids = ['111', '222', '333', '444', '555', '666']
            tree_dir = entry.Tree('12', '1000')
            rule_dir = entry.RuleChanges()
            vers_dir = entry.Version('12', '1000')
            # Existing trees
            (tree_dir / '222').write(Node())
            (tree_dir / '555').write(Node())

            deps = fill_with_rules.dependencies(
                tree_dir, version_ids, '12', '1000')

            # First is skipped, as we can't build it from a rule
            self.assertNotIn(str(tree_dir / '111'), deps)
            # Second can also be skipped as a tree already exists
            self.assertEqual(deps.dependencies(str(tree_dir / '222')), [])
            # Third relies on the associated versions and the second tree
            self.assertItemsEqual(
                deps.dependencies(str(tree_dir / '333')),
                [str(tree_dir / '222'), str(rule_dir / '333'),
                 str(vers_dir / '333')])
            # Fourth relies on the third, even though it's not been built
            self.assertItemsEqual(
                deps.dependencies(str(tree_dir / '444')),
                [str(tree_dir / '333'), str(rule_dir / '444'),
                 str(vers_dir / '444')])
            # Fifth can be skipped as the tree already exists
            self.assertEqual(deps.dependencies(str(tree_dir / '555')), [])
            # Six relies on the fifth
            self.assertItemsEqual(
                deps.dependencies(str(tree_dir / '666')),
                [str(tree_dir / '555'), str(rule_dir / '666'),
                 str(vers_dir / '666')])

    def test_derived_from_rules(self):
        """Should filter a set of version ids to only those with a dependency
        on changes derived from a rule"""
        with self.cli.isolated_filesystem():
            tree_dir = entry.Tree('12', '1000')

            deps = dependency.Graph()
            deps.add(tree_dir / 111, entry.Annual(12, 1000, 2001))
            deps.add(tree_dir / 222, entry.RuleChanges(222))
            deps.add(tree_dir / 333, entry.RuleChanges(333))
            deps.add(tree_dir / 333, entry.Version(333))
            derived = fill_with_rules.derived_from_rules(
                ['111', '222', '333', '444'], deps, tree_dir)
            self.assertEqual(derived, ['222', '333'])
