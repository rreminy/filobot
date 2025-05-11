import json
import logging
import os
import sys
import time
import datetime
import aiohttp
import asyncio
import async_timeout
import discord.ext
import filobot.constants.zones as ZONES
from filobot.utilities.worlds import Worlds
from filobot.filobot import hunt_manager, log

# noinspection PyBroadException
async def bear_handler(self, data):
    try:
        if data is not None and type(data) == dict and len(data) > 1:
            if 'Notification' in data and data['Notification'] == "FoundReport" and 'Reporter' in data and data['Reporter'] != "" and 'World' in data:
                instance = int(data['Hunt'][-1]) if data['Hunt'][-2] == " " and data['Hunt'][-1].isdigit() else 0
                huntName = data['huntName'] if instance else data['huntName'][:-2]
                world = data['World']                
            if 'huntName' in data:
                instance = int(data['huntName'][-1]) if data['huntName'][-2] == " " and data['huntName'][-1].isdigit() else 0
                huntName = data['huntName'] if instance else data['huntName'][:-2]

                if huntName.lower() in hunt_manager.get_marks_info() and 'lastDeathTime' in data and 'expectMinTime' in data:
                    lastAlive = False if int(data['lastDeathTime']) > int(data['expectMinTime']) else True

                    if lastAlive:
                        bearHunt = await hunt_manager.bear.update_bear(data, hunt_manager.get_marks_info()[huntName.lower()], huntName, instance)

                        if bearHunt is not None:
                            await hunt_manager.recheck_trackers('FeedListener2', huntName, bearHunt, instance)
            if 'fateName' in data and 'completed' in data:
                progress = 100 if data['completed'] else 0
                instance = int(data['fateName'][-1]) if data['fateName'][-2] == " " and data['fateName'][-1].isdigit() else 1
                if progress == 100 and data['fateId'] in hunt_manager.bear.fates_info:
                    fateStruct = {
                        'progress': 100,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': data['worldName'],
                        'id': data['fateId'],
                        'state': 1,
                        'x': 1,
                        'y': 1,
                        'i': instance,
                        'lastReported': datetime.datetime.fromtimestamp(int((f"{data['lastDeath']}").split('.')[0][:-3]), datetime.timezone.utc).isoformat(),
                        'zoneID': f"{zones.id(hunt_manager.bear.fates_info[data['fateId']]['ZoneName'])}"
                    }

                    await _process_data('FeedListener2', fateStruct, None)
    except:
        log.exception(data)
        log.exception("Exception occurred in feed listener associated with bear while processing last message")
        pass

class Bear:
    CACHE_TTL = 10
    ENDPOINT_BASE = 'https://api.ffxivsonar.com/horus/'

    def _get_endpoint(self, datacenter: str):
        return f"{self.ENDPOINT_BASE}{datacenter}"

    def _get_endpoints(self):
        ret = []
        for datacenter in Worlds.get_datacenters():
            if datacenter is not None and len(datacenter) > 0:
                ret.append(self._get_endpoint(datacenter))
        return ret

    def __init__(self, bot: discord.ext.commands.Bot):
        self._log = logging.getLogger(__name__)
        self._bot = bot

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json'), 'r', encoding='utf-8') as json_file:
            self.marks_info = json.load(json_file)

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'fates_info.json'), 'r', encoding='utf-8') as json_file:
            self.fates_info = json.load(json_file)

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'achievementfates_info.json'), 'r', encoding='utf-8') as json_file:
            self.fates_info.update(json.load(json_file))

        self._cached_response = {}
        self._cached_time = 0

        self._bear = {}

    async def update_bear(self, data, hunt_data, huntName, instance):
        world = data['worldName']

        if not world in self._bear:
            self._bear[world] = {}

        if instance == 0:
            instance = 0 if 'instance' not in data else data['instance']

        _key = huntName.strip().lower() + f"_{instance}"

        timer = {
            'Id': hunt_data['ID'],
            'world': world,
            'minRespawn': float(hunt_data['MinSpawn']),
            'maxRespawn': float(hunt_data['MaxSpawn']),
            'lastDeath': True,
            'openDate': float(data['expectMinTime']),
            'maxDate': float(data['expectMaxTime']),
            'lastAlive': float(data['lastDeathTime']),
            'lastTryUnix': float(0.0),
            'lastTryUser': "Compatibility",
            'lastMark': float(data['lastDeathTime']),
            'ins': instance
        }

        self._bear[world][_key] = timer

        return BearHunt(hunt_data, timer, timer['ins'])

    async def update(self):
        if time.time() <= self._cached_time + self.CACHE_TTL:
            self._log.debug("Data already up to date")
        else:
            self._log.info('Querying')
            async with aiohttp.ClientSession() as session:
                for endpoint in self._get_endpoints():
                    self._log.debug(f"Querying: {endpoint}")
                    try:
                        response = json.loads(await self._fetch(session, endpoint))
                        self._cached_response.update(response)
                    except Exception:
                        self._log.exception(f"Exception caught while querying {endpoint}")
            self._cached_time = time.time()

    async def load(self, world: str):
        response = self._cached_response
        if world not in response.keys():
            #raise LookupError(f"""World {world} does not exist""")
            return None

        timers = response[world]['timers']

        hunts = {}
        for key, timer in timers.items():
            hunt_data = self.id_to_hunt(timer['Id'])
            _key = hunt_data['Name'].strip().lower() + f"_{timer['ins']}"
            if world in self._bear and _key in self._bear[world] and (self._bear[world][_key]['openDate'] > self._bear[world][_key]['lastAlive']) and (self._bear[world][_key]['lastAlive'] > timer['openDate']):
                timer = self._bear[world][_key]
            hunts[_key] = BearHunt(hunt_data, timer, timer['ins'])

        return hunts

    def id_to_hunt(self, id: str):
        """
        Map Horus hunt ID's to actual hunts
        """
        id = str(id)
        if id not in self.marks_info:
            raise LookupError(f"""Hunt ID {id} does not exist""")

        return self.marks_info[id]

    def id_to_fate(self, id: str):
        """
        Map Horus FATE ID's to actual FATEs
        """
        id = str(id)
        if id not in self.fates_info:
            raise LookupError(f"""FATE ID {id} does not exist""")

        return self.fates_info[id]

    async def _fetch(self, session, url):
        with async_timeout.timeout(15):
            async with session.get(url) as response:
                return await response.text()

class BearHunt:
    STATUS_MAXED  = 'spawn forced'
    STATUS_OPENED = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_DIED   = 'dead'

    def __init__(self, hunt_data, timer_data, instance=1):
        if instance == 0:
            instance = 1

        # Hunt data
        self.name = hunt_data['Name']
        self.instance = instance  # 0 = Not an instanced zone, 1-3 = instance number
        self.rank = hunt_data['Rank']
        self.image = hunt_data['Image'] if "Image" in hunt_data else ""
        self.zone = hunt_data['ZoneName']
        self.region = hunt_data['RegionName'] if "RegionName" in hunt_data else ""
        self.spawn_trigger = hunt_data['SpawnTrigger'] if "SpawnTrigger" in hunt_data else ""
        self.tips = hunt_data['Tips'] if "Tips" in hunt_data else ""

        # Timer data
        self.world = timer_data['world']
        self.min_respawn = timer_data['minRespawn']
        self.max_respawn = timer_data['maxRespawn']
        self.last_death = timer_data['lastDeath']
        self.open_date = timer_data['openDate']
        self.max_date = timer_data['maxDate']
        self.last_alive = timer_data['lastAlive']
        self.last_try = timer_data['lastTryUnix']
        self.last_try_user = timer_data['lastTryUser']
        self.last_mark = timer_data['lastMark']

        # Parse timers
        self.status = None
        _time = time.time() * 1000
        if _time >= self.max_date:
            self.status = self.STATUS_MAXED
        elif _time >= self.open_date:
            self.status = self.STATUS_OPENED
        elif self.last_death:
            self.status = self.STATUS_DIED
        else:
            self.status = self.STATUS_CLOSED

    def __repr__(self) -> str:
        ret = '{'
        ret += f'"name" : "{self.name}",'
        ret += f'"instance" : "{self.instance}",'
        ret += f'"rank" : "{self.rank}",'
        ret += f'"image" : "{self.image}",'
        ret += f'"zone" : "{self.zone}",'
        ret += f'"spawn_trigger" : "{self.spawn_trigger}",'
        ret += f'"region" : "{self.region}",'
        ret += f'"tips" : "{self.tips}",'

        ret += f'"world" : "{self.world}",'
        ret += f'"min_respawn" : "{self.min_respawn}",'
        ret += f'"max_respawn" : "{self.max_respawn}",'
        ret += f'"last_death" : "{self.last_death}",'
        ret += f'"open_date" : "{self.open_date}",'
        ret += f'"max_date" : "{self.max_date}",'
        ret += f'"last_alive" : "{self.last_alive}",'
        ret += f'"last_try" : "{self.last_try}",'
        ret += f'"last_try_user" : "{self.last_try_user}",'
        ret += f'"last_mark" : "{self.last_mark}"'

        ret += '}'
        return ret;
