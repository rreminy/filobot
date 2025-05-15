import json, logging, time, datetime, aiohttp, async_timeout, discord.ext
import filobot.utilities.zones as zones
from filobot.utilities.worlds import worlds
from filobot.utilities.static_data import marks_info, fates_info
from filobot.utilities.bear import BearHunt

class Tracker:
    CACHE_TTL = 10
    ENDPOINT_BASE = 'https://api.ffxivsonar.com/horus/'

    def _get_endpoint(self, datacenter: str):
        return f"{self.ENDPOINT_BASE}{datacenter}"

    def _get_endpoints(self):
        ret = []
        for datacenter in worlds.get_datacenters():
            if datacenter is not None and len(datacenter) > 0:
                ret.append(self._get_endpoint(datacenter))
        return ret

    def __init__(self, bot: discord.ext.commands.Bot):
        self._log = logging.getLogger(__name__)
        self._bot = bot
        self.marks_info, self.fates_info = marks_info, fates_info
        self._cached_response, self._cached_time = {}, 0
        self._tracker, self._tracked = {}, {}

    async def update_tracker(self, data, hunt_data, huntName, instance):
        world = data['worldName']

        if not world in self._tracker:
            self._tracker[world] = {}

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

        self._tracker[world][_key] = timer

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

        hunt_list = {}
        for key, timer in timers.items():
            hunt_data = self.id_to_hunt(timer['Id'])
            _key = hunt_data['Name'].strip().lower() + f"_{timer['ins']}"
            if world in self._tracker and _key in self._tracker[world] and (self._tracker[world][_key]['openDate'] > self._tracker[world][_key]['lastAlive']) and (self._tracker[world][_key]['lastAlive'] > timer['openDate']):
                timer = self._tracker[world][_key]
            hunt_list[_key] = BearHunt(hunt_data, timer, timer['ins'])

        return hunt_list

    def id_to_hunt(self, id: str):
        # Map Horus hunt ID's to actual hunts
        id = str(id)
        if id not in self.marks_info:
            raise LookupError(f"""Hunt ID {id} does not exist""")

        return self.marks_info[id]

    def id_to_fate(self, id: str):
        # Map Horus FATE ID's to actual FATEs
        id = str(id)
        if id not in self.fates_info:
            raise LookupError(f"""FATE ID {id} does not exist""")

        return self.fates_info[id]

    async def _fetch(self, session, url):
        with async_timeout.timeout(15):
            async with session.get(url) as response:
                return await response.text()

# noinspection PyBroadException
async def bear_handler(self, data):
    from filobot.filobot import hunts, fates, tracker
    try:
        if data is not None and type(data) == dict and len(data) > 1:
            if 'Notification' in data and data['Notification'] == "FoundReport" and 'Reporter' in data and data['Reporter'] != "" and 'World' in data:
                instance = int(data['Hunt'][-1]) if data['Hunt'][-2] == " " and data['Hunt'][-1].isdigit() else 0
                huntName = data['huntName'] if instance else data['huntName'][:-2]
                world = data['World']                
            if 'huntName' in data:
                instance = int(data['huntName'][-1]) if data['huntName'][-2] == " " and data['huntName'][-1].isdigit() else 0
                huntName = data['huntName'] if instance else data['huntName'][:-2]

                if huntName.lower() in hunts.get_marks_info() and 'lastDeathTime' in data and 'expectMinTime' in data:
                    lastAlive = False if int(data['lastDeathTime']) > int(data['expectMinTime']) else True

                    if lastAlive:
                        bearHunt = await tracker.update_tracker(data, hunts.get_marks_info()[huntName.lower()], huntName, instance)

                        if bearHunt is not None:
                            await hunts.recheck('FeedListener2', huntName, bearHunt, instance)
            if 'fateName' in data and 'completed' in data:
                progress = 100 if data['completed'] else 0
                instance = int(data['fateName'][-1]) if data['fateName'][-2] == " " and data['fateName'][-1].isdigit() else 1
                if progress == 100 and data['fateId'] in tracker.fates_info:
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
                        'zoneID': f"{zones.id(tracker.fates_info[data['fateId']]['ZoneName'])}"
                    }

                    await fates.process('FeedListener2', fateStruct)
    except Exception:
        _log = logging.getLogger(__name__)
        _log.exception(data)
        _log.exception("Exception occurred in feed listener associated with Bear while processing last message")
        pass
