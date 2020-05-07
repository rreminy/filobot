# Configuration constants
from filobot.filobot import hunt_manager

STALE_MULTIPLIER = 1.5
STALE_MULTIPLIER_S = 1.0  # S are killed too quick


class HuntInfo:
    def __init__(self, id: int, name: str, rank: str, expansion: str, zone: str, open_time: float, forced_time: float):
        # Hunt information
        self.id = id
        self.name = name
        self.rank = rank

        # Expansion and zone
        self.expansion = expansion
        self.zone = zone

        # Window
        self.open_time = open_time
        self.forced_time = forced_time
        self.stale_time = forced_time * (STALE_MULTIPLIER_S if rank == 'S' else STALE_MULTIPLIER)


def get(hunt_id: int) -> HuntInfo:
    for mark in hunt_manager.getmarksinfo.values():
        if int(mark['ID']) == hunt_id:
            id = hunt_id
            name = mark['Name']
            rank = mark['Rank']
            zone = mark['Zone']

            if zone in hunt_manager.ARR_ZONES:
                expansion = "ARR"
            elif zone in hunt_manager.HW_ZONES:
                expansion = "HW"
            elif zone in hunt_manager.SB_ZONES:
                expansion = "SB"
            elif zone in hunt_manager.SHB_ZONES:
                expansion = "SHB"
            else:
                expansion = "Unknown"

            open_time = mark['MinSpawn']
            forced_time = mark['MaxSpawn']

            return HuntInfo(id, name, rank, expansion, zone, open_time, forced_time)
