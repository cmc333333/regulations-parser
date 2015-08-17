"""Namespace for collecting the various types of markers"""

import itertools
import string

from regparser.utils import roman_nums


lower = tuple(string.ascii_lowercase)
upper = tuple(string.ascii_uppercase)
ints = tuple(str(i) for i in range(1, 51))
roman = tuple(itertools.islice(roman_nums(), 0, 50))
em_ints = tuple('<E T="03">' + i + '</E>' for i in ints)
em_roman = tuple('<E T="03">' + i + '</E>' for i in roman)

# Distinction between types of stars as it indicates how much space they can
# occupy
STARS_TAG = 'STARS'
INLINE_STARS = '* * *'
stars = (STARS_TAG, INLINE_STARS)

NO_MARKER = 'NO_MARKER'
no_marker = (NO_MARKER,)

types = [lower, upper, ints, roman, em_ints, em_roman, stars, no_marker]
