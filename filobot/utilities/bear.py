import time

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
