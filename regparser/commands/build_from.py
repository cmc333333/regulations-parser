import codecs
import hashlib
import logging

import click
try:
    import requests_cache
    requests_cache.install_cache('fr_cache')
except ImportError:
    # If the cache library isn't present, do nothing -- we'll just make full
    # HTTP requests rather than looking it up from the cache
    pass

from regparser.builder import (
    LayerCacheAggregator, tree_and_builder, Checkpointer, NullCheckpointer,
    Builder)
from regparser.diff.tree import changes_between
from regparser.tree.struct import FrozenNode

logger = logging.getLogger('build_from')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


# @profile
def parse_regulation(filename, title, act_title, act_section, checkpoint_dir,
                     doc_number):
    """ Run the parser on the specified command-line arguments. Broken out
        into separate function to assist in profiling.
    """

    act_title_and_section = [act_title, act_section]
    #   First, the regulation tree

    reg_tree, builder = tree_and_builder(filename, title, checkpoint_dir,
                                         doc_number)

    builder.write_notices()

    #   Always do at least the first reg
    logger.info("Version %s", builder.doc_number)
    builder.write_regulation(reg_tree)
    layer_cache = LayerCacheAggregator()

    builder.gen_and_write_layers(reg_tree, act_title_and_section, layer_cache)
    layer_cache.replace_using(reg_tree)

    if generate_diffs:
        generate_diffs(reg_tree, act_title_and_section, builder, layer_cache)


def generate_diffs(reg_tree, act_title_and_section, builder, layer_cache):
    """ Generate all the diffs for the given regulation. Broken out into
        separate function to assist with profiling so it's easier to determine
        which parts of the parser take the most time """
    doc_number, checkpointer = builder.doc_number, builder.checkpointer
    all_versions = {doc_number: FrozenNode.from_node(reg_tree)}

    for last_notice, old, new_tree, notices in builder.revision_generator(
            reg_tree):
        version = last_notice['document_number']
        logger.info("Version %s", version)
        all_versions[version] = FrozenNode.from_node(new_tree)
        builder.doc_number = version
        builder.write_regulation(new_tree)
        layer_cache.invalidate_by_notice(last_notice)
        builder.gen_and_write_layers(new_tree, act_title_and_section,
                                     layer_cache, notices)
        layer_cache.replace_using(new_tree)
        del last_notice, old, new_tree, notices     # free some memory

    label_id = reg_tree.label_id()
    writer = builder.writer
    del reg_tree, layer_cache, builder  # free some memory

    # now build diffs - include "empty" diffs comparing a version to itself
    for lhs_version, lhs_tree in all_versions.iteritems():
        for rhs_version, rhs_tree in all_versions.iteritems():
            changes = checkpointer.checkpoint(
                "-".join(["diff", lhs_version, rhs_version]),
                lambda: dict(changes_between(lhs_tree, rhs_tree)))
            writer.diff(
                label_id, lhs_version, rhs_version
            ).write(changes)


def build_by_notice(filename, title, act_title, act_section,
                    notice_doc_numbers, doc_number=None, checkpoint=None):

    with codecs.open(filename, 'r', 'utf-8') as f:
        reg = f.read()
        file_digest = hashlib.sha256(reg.encode('utf-8')).hexdigest()

    if checkpoint:
        checkpointer = Checkpointer(checkpoint)
    else:
        checkpointer = NullCheckpointer()

    # build the initial tree
    reg_tree = checkpointer.checkpoint(
        "init-tree-" + file_digest,
        lambda: Builder.reg_tree(reg))

    title_part = reg_tree.label_id()

    if doc_number is None:
        doc_number = Builder.determine_doc_number(reg, title, title_part)

    checkpointer.suffix = ":".join(
        ["", title_part, str(args.title), doc_number])

    # create the builder
    builder = Builder(cfr_title=title,
                      cfr_part=title_part,
                      doc_number=doc_number,
                      checkpointer=checkpointer)

    builder.fetch_notices_json()

    for notice in notice_doc_numbers:
        builder.build_notice_from_doc_number(notice)

    builder.write_regulation(reg_tree)
    layer_cache = LayerCacheAggregator()

    act_title_and_section = [act_title, act_section]

    builder.gen_and_write_layers(reg_tree, act_title_and_section, layer_cache)
    layer_cache.replace_using(reg_tree)

    if args.generate_diffs:
        generate_diffs(reg_tree, act_title_and_section, builder, layer_cache)


@click.command()
@click.argument('filename',
                type=click.Path(exists=True, dir_okay=False, readable=True))
@click.argument('title', type=int)
@click.option('--act_title', type=int, default=0,
              help=('Title of the act of congress providing authority for '
                    'this regulation'))
@click.option('--act_section', type=int, default=0,
              help=('Section of the act of congress providing authority for '
                    'this regulation'))
@click.option('--generate-diffs/--no-generate-diffs', default=True)
@click.option('--checkpoint', help='Directory to save checkpoint data',
              type=click.Path(file_okay=False, readable=True, writable=True))
@click.option('--version-identifier',
              help=('Do not try to derive the version information. (Only use '
                    'if the regulation has no electronic final rules on '
                    'federalregister.gov, i.e. has not changed since before '
                    '~2000)'))
@click.option('--last-notice', help='the last notice to be used')
@click.option('--operation')
@click.option('--notices-to-apply', nargs=-1)
# @profile
def build_from(filename, title, act_title, act_section, generate_diffs,
               checkpoint, version_identifier, last_notice, operation,
               notices_to_apply):
    """Build all data from provided xml. Reads the provided file and builds
    all versions of the regulation, its layers, etc. that follow.

    \b
    FILENAME: XML file containing the regulation
    TITLE: CFR title
    """
    if operation == 'build_by_notice':
        build_by_notice(filename, title, act_title, act_section,
                        notices_to_apply, last_notice, checkpoint)
    else:
        parse_regulation(filename, title, act_title, act_section, checkpoint,
                         version_identifier)
