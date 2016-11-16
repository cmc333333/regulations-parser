import click

from regparser.commands.annual_editions import annual_editions
from regparser.commands.current_version import current_version
from regparser.commands.diffs import diffs
from regparser.commands.ecfr import ecfr
from regparser.commands.fill_with_rules import fill_with_rules
from regparser.commands.layers import layers
from regparser.commands.versions import versions
from regparser.commands.write_to import write_to


@click.command()
@click.argument('cfr_title', type=int)
@click.argument('cfr_part', type=int)
@click.argument('output', envvar='EREGS_OUTPUT_DIR')
@click.option('--source', default='ecfr',
              type=click.Choice(['latest-annual', 'ecfr', 'fr-compilation']),
              help="Where to find the regulation data.")
@click.pass_context
def pipeline(ctx, cfr_title, cfr_part, output, source):
    """Full regulation parsing pipeline. Consists of retrieving and parsing
    annual edition, attempting to parse final rules in between, deriving
    layers and diffs, and writing them to disk or an API

    \b
    --source values:
    latest-annual: Use only the most recent annual edition of the (full)
        regulation. Does not include history and may be out of date.
    ecfr: Use only the current, up-to-date eCFR data. Does not generate
        history.
    fr-compilation: The "classic" mode, this combines annual editions with
        Federal Register notices to build a history of the regulation. This is
        the most fragile source.

    \b
    OUTPUT can be a
    * directory (if it does not exist, it will be created)
    * uri (the base url of an instance of regulations-core)
    * a directory prefixed with "git://". This will export to a git
      repository"""
    params = {'cfr_title': cfr_title, 'cfr_part': cfr_part}
    if source == 'latest-annual':
        ctx.invoke(current_version, **params)
    elif source == 'ecfr':
        ctx.invoke(ecfr, **params)
    else:
        ctx.invoke(versions, **params)
        ctx.invoke(annual_editions, **params)
        ctx.invoke(fill_with_rules, **params)
    ctx.invoke(layers, **params)
    ctx.invoke(diffs, **params)
    ctx.invoke(write_to, output=output, **params)
