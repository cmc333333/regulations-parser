#!/usr/bin/env python

import codecs
import logging
import argparse


try:
    import requests_cache
    requests_cache.install_cache('fr_cache')
except ImportError:
    # If the cache library isn't present, do nothing -- we'll just make full
    # HTTP requests rather than looking it up from the cache
    pass

from regparser.diff import treediff
from regparser.builder import Builder, LayerCacheAggregator

logger = logging.getLogger('build_from')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

# @profile
def parse_regulation(args):
    """ Run the parser on the specified command-line arguments. Broken out
    into separate function to assist in profiling.
    """
    with codecs.open(args.filename, 'r', 'utf-8') as f:
        reg = f.read()

    #   First, the regulation tree
    reg_tree = Builder.reg_tree(reg)

    title_part = reg_tree.label_id()

    doc_number = Builder.determine_doc_number(reg, args.title, title_part)
    if not doc_number:
        raise ValueError("Could not determine document number")

    act_title_and_section = [args.act_title, args.act_section]

    #   Run Builder
    builder = Builder(cfr_title=args.title,
                      cfr_part=reg_tree.label_id(),
                      doc_number=doc_number)
    builder.write_notices()

    #   Always do at least the first reg
    logger.info("Version %s", doc_number)
    builder.write_regulation(reg_tree)
    layer_cache = LayerCacheAggregator()
    builder.gen_and_write_layers(reg_tree, act_title_and_section, layer_cache)
    layer_cache.replace_using(reg_tree)

    if args.generate_diffs:
        generate_diffs(doc_number, reg_tree, act_title_and_section, builder,
                       layer_cache)


def generate_diffs(doc_number, reg_tree, act_title_and_section, builder,
                   layer_cache):
    """ Generate all the diffs for the given regulation. Broken out into
    separate function to assist with profiling so it's easier to determine
    which parts of the parser take the most time
    """

    all_versions = {doc_number: reg_tree}

    for last_notice, old, new_tree, notices in builder.revision_generator(
            reg_tree):
        version = last_notice['document_number']
        logger.info("Version %s", version)
        all_versions[version] = new_tree
        builder.doc_number = version
        builder.write_regulation(new_tree)
        layer_cache.invalidate_by_notice(last_notice)
        builder.gen_and_write_layers(new_tree, act_title_and_section,
                                     layer_cache, notices)
        layer_cache.replace_using(new_tree)

    # now build diffs - include "empty" diffs comparing a version to itself
    for lhs_version, lhs_tree in all_versions.iteritems():
        for rhs_version, rhs_tree in all_versions.iteritems():
            comparer = treediff.Compare(lhs_tree, rhs_tree)
            comparer.compare()
            builder.writer.diff(
                reg_tree.label_id(), lhs_version, rhs_version
            ).write(comparer.changes)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Regulation parser')
    parser.add_argument('filename',
                        help='XML file containing the regulation')
    parser.add_argument('title', type=int, help='Title number')
    parser.add_argument('act_title', type=int, help='Act title',
                        action='store')
    parser.add_argument('act_section', type=int, help='Act section')
    parser.add_argument('--generate-diffs', type=bool, help='Generate diffs?',
                        required=False, default=True)

    args = parser.parse_args()
    parse_regulation(args)
