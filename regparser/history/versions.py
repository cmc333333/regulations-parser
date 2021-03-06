from collections import namedtuple
from datetime import datetime
import json


class Version(namedtuple('Version', ['identifier', 'published', 'effective'])):
    def json(self):
        return json.dumps({'identifier': self.identifier,
                           'published': self.published.isoformat(),
                           'effective': self.effective.isoformat()})

    @staticmethod
    def from_json(json_str):
        json_dict = json.loads(json_str)
        for key in ('published', 'effective'):
            json_dict[key] = datetime.strptime(json_dict[key],
                                               '%Y-%m-%d').date()
        return Version(**json_dict)

    def __lt__(self, other):
        """We'd like to sort in a slightly different field order"""
        left = (self.effective, self.published, self.identifier)
        right = (other.effective, other.published, other.identifier)
        return left < right
