import codecs
import os
from parser.tree.appendix.tree import trees_from as appendix_trees
from parser.tree.interpretation.tree import build as build_interp_tree
from parser.tree.reg_text import build_reg_text_tree
from parser.tree.struct import walk
from parser.tree.supplement import find_supplement_start
import sys

def write_node(node, root_dir):
    dir_prefix = os.sep.join([root_dir] + node['label']['parts']) + os.sep
    if not os.path.exists(dir_prefix):
        os.makedirs(dir_prefix)
    with codecs.open(dir_prefix + "text.txt", 'w', encoding='utf-8') as f:
        f.write(node['text'])
    if 'title' in node['label']:
        with codecs.open(dir_prefix + "title.txt", 'w', encoding='utf-8') as f:
            f.write(node['label']['title'])


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print "Usage: python write_tree.py filesystemroot/"
        exit()
    with codecs.open('rege.txt', encoding='utf-8') as f:
        reg = unicode(f.read())

    interp = reg[find_supplement_start(reg):]

    reg_tree = build_reg_text_tree(reg, 1005)
    interp_tree = build_interp_tree(interp, 1005)
    appendix_trees = appendix_trees(reg, 1005, reg_tree['label'])

    reg_tree['children'].extend(appendix_trees)
    reg_tree['children'].append(interp_tree)

    root_dir = sys.argv[1]
    if not root_dir.endswith(os.sep):
        root_dir += os.sep

    walk(reg_tree, lambda node: write_node(node, root_dir))
