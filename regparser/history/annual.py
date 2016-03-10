# vim: set encoding=utf-8
from collections import namedtuple
from datetime import date, datetime
import logging
import os
import re

import requests

from regparser.federalregister import fetch_notice_json
from regparser.history.delays import modify_effective_dates
from regparser.index import xml_sync
from regparser.notice.build import build_notice
from regparser.tree.xml_parser.xml_wrapper import XMLWrapper
import settings


CFR_BULK_URL = ("https://www.gpo.gov/fdsys/bulkdata/CFR/{year}/title-{title}/"
                "CFR-{year}-title{title}-vol{volume}.xml")
CFR_PART_URL = ("https://www.gpo.gov/fdsys/pkg/"
                "CFR-{year}-title{title}-vol{volume}/xml/"
                "CFR-{year}-title{title}-vol{volume}-part{part}.xml")

# Matches any of the following:
#    Parts 200 to 219
#    Parts 200 to end
#    Part 52 (§§ 52.1019 to 52.2019)
# Note: The outer parentheses seem to be required by Python, although they
#       shouldn't be
PART_SPAN_REGEX = re.compile(
    r'.*parts? ('
    r'(?P<span>(?P<start>\d+) to ((?P<end>\d+)|(?P<end_literal>end)))'
    r'|((?P<single_part>\d+) \(.*\))'
    r'.*)',
    flags=re.IGNORECASE)
logger = logging.getLogger(__name__)


class Volume(namedtuple('Volume', ['year', 'title', 'vol_num'])):
    def __init__(self, year, title, vol_num):
        super(Volume, self).__init__(year, title, vol_num)
        self.url = CFR_BULK_URL.format(year=year, title=title, volume=vol_num)
        self._response, self._exists, self._part_span = None, None, None

    @property
    def response(self):
        if self._response is None:
            logger.debug("GET %s", self.url)
            self._response = requests.get(self.url, stream=True)
        return self._response

    @property
    def exists(self):
        return self.response.status_code == 200

    @property
    def part_span(self):
        """Calculate and memoize the range of parts this volume covers"""
        if self._part_span is None:
            self._part_span = False
            part_string = ''

            for line in self.response.iter_lines():
                if '<PARTS>' in line:
                    part_string = line
                    break
            if part_string:
                match = PART_SPAN_REGEX.match(part_string)
                if match and match.group('span'):
                    start = int(match.group('start'))
                    if match.group('end_literal'):
                        end = None
                    else:
                        end = int(match.group('end'))
                    self._part_span = (start, end)
                elif match:
                    start = int(match.group('single_part'))
                    self._part_span = (start, start)
                else:
                    logger.warning("Can't parse: %s", part_string)
            else:
                logger.warning('No <PARTS> in %s. Assuming this volume '
                               'contains all of the regs', self.url)
                self._part_span = (1, None)
        return self._part_span

    @property
    def publication_date(self):
        return date(self.year, publication_month(self.title), 1)

    def should_contain(self, part):
        """Does this volume contain the part number requested?"""
        if self.part_span:
            (start, end) = self.part_span
            if start > part:
                return False
            elif end is None:
                return True
            else:
                return end >= part
        else:
            return False

    def find_part_xml(self, part):
        """Pull the XML for an annual edition, first checking locally"""
        logger.info("Find Part xml for %s CFR %s", self.title, part)
        url = CFR_PART_URL.format(year=self.year, title=self.title,
                                  volume=self.vol_num, part=part)
        filename = url.split('/')[-1]
        for xml_path in settings.LOCAL_XML_PATHS + [xml_sync.GIT_DIR]:
            xml_path = os.path.join(xml_path, 'annual', filename)
            logger.debug("Checking locally for file %s", xml_path)
            if os.path.isfile(xml_path):
                with open(xml_path) as f:
                    return XMLWrapper(f.read(), xml_path)
        logger.debug("GET %s", url)
        response = requests.get(url)
        if response.status_code == 200:
            return XMLWrapper(response.content, url)


def annual_edition_for(title, notice):
    """Annual editions are published for different titles at different
    points throughout the year. Find the 'next' annual edition"""
    eff_date = datetime.strptime(notice['effective_on'], '%Y-%m-%d').date()
    return date_of_annual_after(title, eff_date).year


def publication_month(cfr_title):
    """Annual editions are published for different titles at different points
    throughout the year. Return the month associated with this CFR title"""
    if cfr_title <= 16:
        return 1
    elif cfr_title <= 27:
        return 4
    elif cfr_title <= 41:
        return 7
    else:
        return 10


def date_of_annual_after(title, eff_date):
    """Return the date of the _first_ annual edition which should contain any
    changes on `eff_date`. This date may well be in the future"""
    publication_date = date(eff_date.year, publication_month(title), 1)
    if eff_date <= publication_date:
        return publication_date
    else:
        return publication_date.replace(year=eff_date.year + 1)


def find_volume(year, title, part):
    """Annual editions have multiple volume numbers. Try to find the volume
    that we care about"""
    vol_num = 1
    volume = Volume(year, title, vol_num)
    while volume.exists:
        if volume.should_contain(part):
            return volume
        vol_num += 1
        volume = Volume(year, title, vol_num)
    return None


def first_notice_and_xml(title, part):
    """Find the first annual xml and its associated notice"""
    logger.debug("Finding first annual notice+xml - %s CFR %s",
                 title, part)
    notices = [build_notice(title, part, n, fetch_xml=False)
               for n in fetch_notice_json(title, part, only_final=True)
               if n['full_text_xml_url'] and n['effective_on']]
    modify_effective_dates(notices)

    notices = sorted(notices,
                     key=lambda n: (n['effective_on'], n['publication_date']))

    years = {}
    for n in notices:
        year = annual_edition_for(title, n)
        years[year] = n

    for year, notice in sorted(years.iteritems()):
        volume = find_volume(year, title, part)
        if volume:
            part_xml = volume.find_part_xml(part)
            if part_xml is not None:
                return (notice, part_xml)
