import json
import logging
import os
import sys
import time
import urllib.request


class Horus:

    ENDPOINT = 'https://horus-hunts.net/Timers/GetDcTimers/?DC=Crystal'

    def __init__(self):
        self._log = logging.getLogger(__name__)

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json')) as json_file:
            self.marks_info = json.load(json_file)

        # with open('data\\marks_info.json') as json_file:
        #     self.marks_info = json.load(json_file)

    def load(self, world: str):
        """
        Load Horus data on the specified world
        """
        # Currently hardcoded to the Crystal DC; we might add support for other DC's later
        crystal = json.load(urllib.request.urlopen(self.ENDPOINT))

        if world not in crystal.keys():
            raise LookupError(f"""World {world} does not exist""")
        timers = crystal[world]['timers']

        hunts = {}
        for id, timer in timers.items():
            hunt_data = self.id_to_hunt(id)
            hunts[hunt_data['Name']] = HorusHunt(hunt_data, timer)

        return hunts

    def id_to_hunt(self, id):
        """
        Map Horus hunt ID's to actual hunts
        """
        if id not in self.marks_info:
            raise LookupError(f"""ID {id} does not exist""")

        return self.marks_info[id]


class HorusHunt:

    STATUS_MAXED  = 'spawn forced'
    STATUS_OPENED = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_DIED   = 'dead'

    def __init__(self, hunt_data, timer_data):
        # Hunt data
        self.name = hunt_data['Name']
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

