import logging
import re
import urllib.request
import bs4

from bs4 import BeautifulSoup


class XivHunt:

    WORLDS = {
        'Aegis'       : 'https://xivhunt.net/home/HuntTablePartial/90',
        'Alexander'   : 'https://xivhunt.net/home/HuntTablePartial/43',
        'Anima'       : 'https://xivhunt.net/home/HuntTablePartial/44',
        'Asura'       : 'https://xivhunt.net/home/HuntTablePartial/23',
        'Atomos'      : 'https://xivhunt.net/home/HuntTablePartial/68',
        'Bahamut'     : 'https://xivhunt.net/home/HuntTablePartial/69',
        'Balmung'     : 'https://xivhunt.net/home/HuntTablePartial/91',
        'Behemoth'    : 'https://xivhunt.net/home/HuntTablePartial/78',
        'Belias'      : 'https://xivhunt.net/home/HuntTablePartial/24',
        'Brynhildr'   : 'https://xivhunt.net/home/HuntTablePartial/34',
        'Cactuar'     : 'https://xivhunt.net/home/HuntTablePartial/79',
        'Carbuncle'   : 'https://xivhunt.net/home/HuntTablePartial/45',
        'Cerberus'    : 'https://xivhunt.net/home/HuntTablePartial/80',
        'Chocobo'     : 'https://xivhunt.net/home/HuntTablePartial/70',
        'Coeurl'      : 'https://xivhunt.net/home/HuntTablePartial/74',
        'Diabolos'    : 'https://xivhunt.net/home/HuntTablePartial/62',
        'Durandal'    : 'https://xivhunt.net/home/HuntTablePartial/92',
        'Excalibur'   : 'https://xivhunt.net/home/HuntTablePartial/93',
        'Exodus'      : 'https://xivhunt.net/home/HuntTablePartial/53',
        'Faerie'      : 'https://xivhunt.net/home/HuntTablePartial/54',
        'Famfrit'     : 'https://xivhunt.net/home/HuntTablePartial/35',
        'Fenrir'      : 'https://xivhunt.net/home/HuntTablePartial/46',
        'Garuda'      : 'https://xivhunt.net/home/HuntTablePartial/58',
        'Gilgamesh'   : 'https://xivhunt.net/home/HuntTablePartial/63',
        'Goblin'      : 'https://xivhunt.net/home/HuntTablePartial/81',
        'Gungnir'     : 'https://xivhunt.net/home/HuntTablePartial/94',
        'Hades'       : 'https://xivhunt.net/home/HuntTablePartial/47',
        'Hyperion'    : 'https://xivhunt.net/home/HuntTablePartial/95',
        'Ifrit'       : 'https://xivhunt.net/home/HuntTablePartial/59',
        'Ixion'       : 'https://xivhunt.net/home/HuntTablePartial/48',
        'Jenova'      : 'https://xivhunt.net/home/HuntTablePartial/40',
        'Kujata'      : 'https://xivhunt.net/home/HuntTablePartial/49',
        'Lamia'       : 'https://xivhunt.net/home/HuntTablePartial/55',
        'Leviathan'   : 'https://xivhunt.net/home/HuntTablePartial/64',
        'Lich'        : 'https://xivhunt.net/home/HuntTablePartial/36',
        'Louisoix'    : 'https://xivhunt.net/home/HuntTablePartial/83',
        'Malboro'     : 'https://xivhunt.net/home/HuntTablePartial/75',
        'Mandragora'  : 'https://xivhunt.net/home/HuntTablePartial/82',
        'Masamune'    : 'https://xivhunt.net/home/HuntTablePartial/96',
        'Mateus'      : 'https://xivhunt.net/home/HuntTablePartial/37',
        'Midgardsormr': 'https://xivhunt.net/home/HuntTablePartial/65',
        'Moogle'      : 'https://xivhunt.net/home/HuntTablePartial/71',
        'Odin'        : 'https://xivhunt.net/home/HuntTablePartial/66',
        'Omega'       : 'https://xivhunt.net/home/HuntTablePartial/39',
        'Pandaemonium': 'https://xivhunt.net/home/HuntTablePartial/28',
        'Phoenix'     : 'https://xivhunt.net/home/HuntTablePartial/56',
        'Ragnarok'    : 'https://xivhunt.net/home/HuntTablePartial/97',
        'Ramuh'       : 'https://xivhunt.net/home/HuntTablePartial/60',
        'Ridill'      : 'https://xivhunt.net/home/HuntTablePartial/98',
        'Sargatanas'  : 'https://xivhunt.net/home/HuntTablePartial/99',
        'Shinryu'     : 'https://xivhunt.net/home/HuntTablePartial/29',
        'Shiva'       : 'https://xivhunt.net/home/HuntTablePartial/67',
        'Siren'       : 'https://xivhunt.net/home/HuntTablePartial/57',
        'Tiamat'      : 'https://xivhunt.net/home/HuntTablePartial/76',
        'Titan'       : 'https://xivhunt.net/home/HuntTablePartial/61',
        'Tonberry'    : 'https://xivhunt.net/home/HuntTablePartial/72',
        'Typhon'      : 'https://xivhunt.net/home/HuntTablePartial/50',
        'Ultima'      : 'https://xivhunt.net/home/HuntTablePartial/51',
        'Ultros'      : 'https://xivhunt.net/home/HuntTablePartial/77',
        'Unicorn'     : 'https://xivhunt.net/home/HuntTablePartial/30',
        'Valefor'     : 'https://xivhunt.net/home/HuntTablePartial/52',
        'Yojimbo'     : 'https://xivhunt.net/home/HuntTablePartial/31',
        'Zalera'      : 'https://xivhunt.net/home/HuntTablePartial/41',
        'Zeromus'     : 'https://xivhunt.net/home/HuntTablePartial/32',
        'Zodiark'     : 'https://xivhunt.net/home/HuntTablePartial/42',
    }

    # Badge classes are used as status indicators
    STATUS_DEAD = 'badge-danger'
    STATUS_OPEN = 'badge-success'
    STATUS_SEEN = 'badge-primary'
    STATUS_AWOL = 'badge-secondary'

    _RE_SEEN = re.compile(r"(?P<seen>\d+:\d+)<br\s?/>(?P<coords>.+)</span>")

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def load(self, world: str):
        """
        Load XIVHunt data on the specified world
        """
        # Make sure we have a valid world
        if world not in self.WORLDS:
            raise LookupError(f"""World {world} does not exist""")

        self._log.info(f"""Querying XIVHunt for hunts on world {world}""")
        page = urllib.request.urlopen(self.WORLDS[world])
        soup = BeautifulSoup(page, 'html.parser')

        hunts = {}
        for item in soup.find_all('li', attrs={'class': 'list-group-item'}):  # type: bs4.element.Tag
            name = item.find('span', attrs={'class': 'huntname'}).text
            info = item.find('span', attrs={'class': 'hunttime'})

            # If this is a fate, skip it
            fate = item.find('img', attrs={'alt': 'FATE'})
            if fate is not None:
                self._log.debug('Refusing to parse Fate entry ' + name)
                continue

            self._log.debug('Parsing XivHunt data for ' + name)

            # Get the rank
            rank = item.find('span').text

            # Dead, open, seen, or missing?
            status = None
            if self.STATUS_DEAD in info.attrs['class']:
                status = 'dead'
            elif self.STATUS_OPEN in info.attrs['class']:
                status = 'open'
            elif self.STATUS_SEEN in info.attrs['class']:
                status = 'seen'
            elif self.STATUS_AWOL in info.attrs['class']:
                status = 'missing'
            else:
                self._log.warning(f"""Cannot parse hunt status for {name} ({info.attrs['class']})""")
                continue

            # If the hunt has been seen, get the coords
            last_seen = None
            coords = None
            if status == 'seen':
                match = self._RE_SEEN.findall(str(info))
                if not match:
                    self._log.warning('Could not parse seen hunt: ' + name)
                    continue

                last_seen, coords = match[0]

            hunts[name.lstrip().rstrip().lower()] = {
                'rank': rank,
                'status': status,
                'last_seen': last_seen,
                'coords': coords
            }

        return hunts
