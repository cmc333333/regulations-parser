import click

from regparser import ecfr as ecfr_lib
from regparser.history.versions import Version
from regparser.index import entry
from regparser.notice.fake import build as build_fake_notice


@click.command()
@click.argument('cfr_title', type=int)
@click.argument('cfr_part', type=int, required=False)
def ecfr(cfr_title, cfr_part=None):
    """Build a regulation tree based on the current eCFR. This will also
    construct a corresponding, empty notice."""
    xml = ecfr_lib.xml_for_title(cfr_title)
    effective = xml.modified
    if cfr_part:
        cfr_parts = [cfr_part]
    else:
        cfr_parts = xml.cfr_parts()

    for part in cfr_parts:
        version_id = '{}-ecfr'.format(part)
        tree = xml.parse_part(part)
        entry.Version(cfr_title, part, version_id).write(
            Version(version_id, effective=effective, published=effective))
        entry.Notice(version_id).write(build_fake_notice(
            version_id, effective, cfr_title, part))
        entry.Tree(cfr_title, part, version_id).write(tree)
