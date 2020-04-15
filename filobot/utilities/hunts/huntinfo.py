# Configuration constants
STALE_MULTIPLIER = 1.5
STALE_MULTIPLIER_S = 1.0 # S are killed too quick


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
    # TODO: well... should be something like _huntinfo[hunt_id]
    return

def _init():
    # TODO: Gigantic initialization function
    return
