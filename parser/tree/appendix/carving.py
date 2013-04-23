import re
from parser.search import segments as split_by_offset
from parser.search import find_start as start_of_heading
from parser.search import find_offsets as start_end_of
from parser.tree.supplement import find_supplement_start

#   Find appendices in the regulation
def appendices(text):
    """Carve out a list of all the appendix offsets."""
    def offsets_fn(remaining_text, idx, excludes):
        return find_next_appendix_offsets(remaining_text)
    return split_by_offset(text, offsets_fn)


def find_next_appendix_offsets(text):
    """Find the start/end of the next appendix. Accounts for supplements"""
    offsets = start_end_of(text, find_appendix_start)
    if offsets is None:
        return None

    start, end = offsets
    supplement_start = find_supplement_start(text)
    if supplement_start != None and supplement_start < start:
        return None
    if supplement_start != None and supplement_start < end:
        return (start, supplement_start)
    return (start, end)


def find_appendix_start(text):
    """Find the start of the appendix (e.g. Appendix A)"""
    return start_of_heading(text, u'Appendix', ur'[A-Z]')


def get_appendix_letter(title, part):
    """Pull out appendix letter from header. Assumes proper format"""
    return re.match(ur'^Appendix ([A-Z]+) to Part %d.*$'%part, title).group(1)


#   Find sections within an appendix
def appendix_sections(text, appendix):
    """Split an appendix into its sections. Return the offsets"""
    def offsets_fn(remaining_text, idx, excludes):
        return find_next_appendix_section_offsets(remaining_text, appendix)
    return split_by_offset(text, offsets_fn)


def find_next_appendix_section_offsets(text, appendix):
    """Find the start/end of the next appendix section."""
    return start_end_of(text, lambda t:find_appendix_section_start(t,
        appendix))


def find_appendix_section_start(text, appendix):
    """Find the start of an appendix section (e.g. A-1 -- Something"""
    match = re.search(ur'%s-\d+' % appendix, text, re.MULTILINE)
    if match:
        return match.start()


def get_appendix_section_number(title, appendix_letter):
    """Pull out appendix section number from header. Assumes proper format"""
    return re.match(ur'^%s-(\d+).*$' % appendix_letter, title).group(1)
