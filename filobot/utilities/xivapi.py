import asyncio
import datetime
import logging
import aiohttp
import discord
import xivapi

# Class / Jobs mapping, assigned and cached when the Job container is initialized
JOBS = {}


class XivApi:

    def __init__(self, api_key):
        self._log = logging.getLogger(__name__)
        self._api_key = api_key

    async def search_character(self, world, forename, surname):
        async with aiohttp.ClientSession() as session:
            client = xivapi.Client(session=session, api_key=self._api_key)

            # Search Lodestone for a character
            search = await client.character_search(
                    world=world,
                    forename=forename,
                    surname=surname
            )

            # No characters found?
            if not search['Results']:
                _error = f"""No character by the name {forename} {surname} found on {world}"""
                self._log.info(_error)
                raise ValueError(_error)

            character = await client.character_by_id(search['Results'][0]['ID'], include_freecompany=True, include_achievements=True, extended=True)
            print(character)
            return Character(character)


class Character:

    GENDER_FEMALE = 'female'
    GENDER_MALE = 'male'

    COLOR_FEMALE = 0xad2742
    COLOR_MALE = 0x275dad

    DATACENTERS = {
        'Crystal': ('Balmung', 'Brynhildr', 'Coeurl', 'Diabolos', 'Goblin', 'Malboro', 'Mateus', 'Zalera'),
        'Aether' : ('Adamantoise', 'Cactuar', 'Faerie', 'Gilgamesh', 'Jenova', 'Midgardsormr', 'Sargatanas', 'Siren'),
        'Primal' : ('Behemoth', 'Excalibur', 'Exodus', 'Famfrit', 'Hyperion', 'Lamia', 'Leviathan', 'Ultros')
    }

    def __init__(self, api_response: dict):
        self.name       = api_response['Character']['Name']
        self.title      = api_response['Character']['Title']['Name']
        self.race       = api_response['Character']['Race']['Name']
        self.tribe      = api_response['Character']['Tribe']['Name']
        self.nameday    = api_response['Character']['Nameday']
        self._ticon     = api_response['Character']['Town']['Icon']
        self.server     = api_response['Character']['Server']
        self.avatar     = api_response['Character']['Avatar']
        self.portrait   = api_response['Character']['Portrait']
        self.bio        = api_response['Character']['Bio']
        self.gender     = self.GENDER_FEMALE if api_response['Character']['Gender'] == 2 else self.GENDER_MALE
        self.points     = api_response['Achievements']['Points']
        self.fc         = api_response['FreeCompany']
        self.updated    = datetime.datetime.utcfromtimestamp(api_response['Character']['ParseDate'])

        self.datacenter = None
        for dc, worlds in self.DATACENTERS.items():
            if self.server in worlds:
                self.datacenter = dc
                break

        self.jobs = {}
        if api_response['Character']['ClassJobs']:
            for job in api_response['Character']['ClassJobs'].values():
                job = Job(job)
                self.jobs[job.name] = job

        self.active_job = Job(api_response['Character']['ActiveClassJob'])

    def embed(self, verified=False):
        embed = discord.Embed()
        embed.title         = self.title
        embed.colour        = self.COLOR_FEMALE if self.gender == self.GENDER_FEMALE else self.COLOR_MALE

        author_name = f"""{self.name} of «{self.fc['Name']}»""" if isinstance(self.fc, dict) else self.name
        if verified:
            author_name = author_name + " ✔️"
        embed.set_author(name=author_name, icon_url=self.avatar)
        embed.set_thumbnail(url=self.active_job.icon)
        embed.set_image(url=self.portrait)
        embed.set_footer(text="Last updated", icon_url=f"""https://xivapi.com{self._ticon}""")
        embed.timestamp = self.updated

        embed.add_field(name="Race", value=f"""{self.race} ({self.tribe})""")
        embed.add_field(name="Server", value=f"""{self.server} ({self.datacenter})""")
        embed.add_field(name="Active job", value=f"""{self.active_job.name} (Level {self.active_job.level})""")
        embed.add_field(name="Achievement points", value="{:,}".format(self.points))

        return embed


class Job:

    def __init__(self, api_response: dict):
        self._log = logging.getLogger(__name__)

        self.name           = api_response['Job']['Name'].title()
        self.level          = api_response['Level']
        self.icon           = f"""https://xivapi.com{api_response['Job']['Icon']}"""
        self.exp_level      = api_response['ExpLevel']
        self.exp_level_max  = api_response['ExpLevelMax']
        self.exp_level_togo = api_response['ExpLevelTogo']


class FreeCompany:

    def __init__(self, id: int, api: XivApi):
        self._log = logging.getLogger(__name__)
