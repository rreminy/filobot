from filobot.utilities.worlds import Worlds


class HuntUtil:
    def getKey(world_id: int, hunt_id: int, instance_id: int) -> str:
        return str(world_id) + '_' + str(hunt_id) + '_' + str(instance_id)

    def getInfo(key:str) -> dict:
        # TODO: Change JS to Python
        let field = key.split('_');
        return {
            world_id: field[0],
            hunt_id: field[1],
            instance_id: field[2]
        }


class HuntStatus:
    def __init__(self):
        raise 'HuntStatus is a static class'

    # Nothing reported yet
    UNKNOWN = 'UNKNOWN' # The bot just started or reports are stale
    STALE = 'UNKNOWN' # alias of UNKNOWN

    # Hunt status
    MAYBE_OPEN = 'MAYBE_OPEN'
    OPEN = 'OPEN'
    FORCED = 'FORCED'
    FOUND = 'FOUND'
    MAYBE_DEAD = 'MAYBE_DEAD' # For untrusted trackers (e.g. Ariyala)
    DEAD = 'DEAD'
