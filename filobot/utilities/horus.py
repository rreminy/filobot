import json
import logging
import os
import sys
import time

import aiohttp
import asyncio
import async_timeout
import discord.ext
from filobot.utilities.worlds import Worlds

class Horus:
    CACHE_TTL = 15
    ENDPOINT_BASE = 'https://horus-hunts.net/Timers/GetDcTimers/?DC='

    def _get_endpoint(self, datacenter: str):
        return f"{self.ENDPOINT_BASE}{datacenter}"

    def _get_endpoints(self):
        ret = []
        for datacenter in Worlds.get_datacenters():
            ret.append(self._get_endpoint(datacenter))
        return ret

    def __init__(self, bot: discord.ext.commands.Bot):
        self._log = logging.getLogger(__name__)
        self._bot = bot

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json')) as json_file:
            self.marks_info = json.load(json_file)

        self._cached_response = {}
        self._cached_time = 0

    async def update_horus(self):
        if time.time() <= self._cached_time + self.CACHE_TTL:
            self._log.debug("Horus data already up to date")
        else:
            self._log.info('Querying Horus')
            async with aiohttp.ClientSession() as session:
                for endpoint in self._get_endpoints():
                    self._log.debug(f"Querying: {endpoint}")
                    try:
                        response = json.loads(await self._fetch(session, endpoint))
                        self._cached_response.update(response)
                    except:
                        self._log.exception(f"Exception caught while querying {endpoint}")
            self._cached_time = time.time()

    async def load(self, world: str):
        response = self._cached_response
        if world not in response.keys():
            raise LookupError(f"""World {world} does not exist""")
        timers = response[world]['timers']

        hunts = {}
        for key, timer in timers.items():
            hunt_data = self.id_to_hunt(timer['Id'])
            hunts[hunt_data['Name'].strip().lower() + f"_{timer['ins']}"] = HorusHunt(hunt_data, timer, timer['ins'])

        return hunts

    def id_to_hunt(self, id: str):
        """
        Map Horus hunt ID's to actual hunts
        """
        id = str(id)
        if id not in self.marks_info:
            raise LookupError(f"""ID {id} does not exist""")

        return self.marks_info[id]

    async def _fetch(self, session, url):
        with async_timeout.timeout(15):
            async with session.get(url) as response:
                return await response.text()


class HorusHunt:

    STATUS_MAXED  = 'spawn forced'
    STATUS_OPENED = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_DIED   = 'dead'

    def __init__(self, hunt_data, timer_data, instance=1):
        # Hunt data
        self.name = hunt_data['Name']
        self.instance = instance  # 0 = Not an instanced zone, 1-3 = instance number
        self.rank = hunt_data['Rank']
        self.image = hunt_data['Image']
        self.zone = hunt_data['ZoneName']
        self.region = hunt_data['RegionName']
        self.spawn_trigger = hunt_data['SpawnTrigger']
        self.tips = hunt_data['Tips']

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
