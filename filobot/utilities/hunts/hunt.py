import time
import typing

# from ...worlds import Worlds
from huntinfo import HuntInfo

# Configuration constants
FOUND_TO_STALE = float(7200) # Time to consider OPEN as UNKNOWN
TIME_TOLERANCE = float(300) # Tolerance time for slightly inaccurate reports

class Hunt:
    def __init__(self, world_id: int, hunt_id: int, instance_id: int):
        # Hunt information
        self._world_id = world_id
        self._hunt_id = hunt_id
        self._instance_id = instance_id

        # Internal information
        self._status = 'UNKNOWN'
        self._last_updated = time.time()
        self._time_since_previous_update = 0
        self._source = ''
        self._coords_x = 0
        self._coords_y = 0

        # Hunt information
        self._info = HuntInfo.get(hunt_id)

    # Almost every function must run this
    def _auto_update_status(self):
        # Initialize variables
        delta = self.get_last_updated_since()
        status = self._status
        info = self._info

        # If there is no information available
        if status == HuntStatus.UNKNOWN:
            # There's nothing to do
            return

        # If hunt is dead or maybe dead
        elif status == HuntStatus.DEAD or status == HuntStatus.MAYBE_DEAD:
            # Its been too long
            if delta > (info.stale_time + TIME_TOLERANCE):
                # I don't know... are players reporting this?
                self._status = HuntStatus.UNKNOWN
            # Time window is forced
            elif delta > info.forced_time:
                # The hunt is forced up
                self._status = HuntStatus.FORCED
            # Time window is open
            elif delta > info.open_time:
                # The hunt may spawn anytime
                self._status = HuntStatus.OPEN
            # Time window is close enough to open
            elif delta > (info.open_time - TIME_TOLERANCE):
                # Window is not technically open yet but accept status changes
                self._status = HuntStatus.MAYBE_OPEN

        # If the hunt window is maybe open
        elif status == HuntStatus.MAYBE_OPEN:
            if delta > (info.stale_time + TIME_TOLERANCE):
                # I don't know... are players reporting this?
                self._status = HuntStatus.UNKNOWN
            # Time window is forced
            elif delta > info.forced_time:
                # The hunt is forced up
                self._status = HuntStatus.FORCED
            # Time window is open
            elif delta > info.open_time:
                # The hunt may spawn anytime
                self._status = HuntStatus.OPEN

        # If the hunt window is open
        elif status == HuntStatus.MAYBE_OPEN:
            if delta > (info.stale_time + TIME_TOLERANCE):
                # I don't know... are players reporting this?
                self._status = HuntStatus.UNKNOWN
            # Time window is forced
            elif delta > info.forced_time:
                # The hunt is forced up
                self._status = HuntStatus.FORCED

        # If the hunt window is forced
        elif status == HuntStatus.MAYBE_OPEN:
            if delta > (info.stale_time + TIME_TOLERANCE):
                # I don't know... are players reporting this?
                self._status = HuntStatus.UNKNOWN

        # If the hunt is found
        elif status == HuntStatus.FOUND:
            # Its been a while
            if delta > (FOUND_TO_STALE + TIME_TOLERANCE):
                # I don't know if its dead or alive
                self._status = HuntStatus.UNKNOWN

        # Just so i know where the function ends...
        # NOTE: The above could probably be optimized
        return


    # Basic Informational functions
    def get_hunt_id(self) -> int:
        return self.hunt_id

    def get_hunt_name(self) -> str:
        return self._info.name

    def get_name(self) -> str: # alias of get_hunt_name
        return self._info.name

    def get_rank(self) -> str:
        return self._info.rank

    def get_world_id(self) -> int:
        return self._world_id

    def get_world(self) -> str:
        return Worlds.get_world(self._world_id)

    def get_zone(self) -> str:
        return self._info.zone

    def get_expansion(self) -> str:
        return self._info.expansion

    def get_instance_id(self) -> int:
        return self._instance_id

    def hunt_info(self) -> HuntInfo:
        return self._info

    def get_coords_x(self) -> float:
        return self._coords_x

    def get_coords_y(self) -> float:
        return self._coords_x

    def get_coords_str(self) -> str:
        return f"(X: {str(self._coords_x)}, Y: {str(self._coords_y)})"

    def get_short_call_string(self) -> str:
        return f"[{self.get_world()}] {self.get_zone()} {str(self.get_coords_str())} i{self.get_instance_id()}"


    # Discord helpers
    def discord_message(self) -> str:
        text = f"self.get_short_call_string"
        if self._status == HuntStatus.DEAD:
            text = f"~~{text}~~ **Killed** *(after how to do self...)*" # TODO: How long
        return text

    def embed_title(self) -> str:
        text = f"Rank {self.get_rank()}: {self.get_name()}"
        if self._status == HuntStatus.DEAD:
            text = f"~~{text}~~ DEAD"
        return text

    def embed_description(self) -> str:
        text = self.get_short_call_string()
        if self._status == HuntStatus.DEAD:
            text = f"~~{text}~~"
        return text

    def embed_footer(self) -> str:
        return self._source


    # Log helpers
    def log_hunt_identification(self) -> str:
        return f"[{self.get_world()}] {self._get_name()} i{self.get_instance_id()}"

    def __log_hunt_status_change_1(self, old_status, new_status) -> str:
        return f"{old_status} => {new_status}"

    def log_text_status_change(self, old_status, new_status) -> str:
        text = f"{self.log_hunt_identification} Status changed: {self.__log_hunt_status_change_1(old_status, new_status)}"
        if new_status == HuntStatus.FOUND:
            text = f"{text} | {self.get_short_call_string()}"
        return text


    # Tracking Informational functions
    def is_open(self) -> bool:
        self._auto_update_status()
        return True if self._status == HuntStatus.OPEN else False

    def is_maybe_open(self) -> bool: # this function consider open as maybe open
        self._auto_update_status()
        return True if self._status == HuntStatus.MAYBE_OPEN or self._status == HuntStatus.OPEN else False

    def is_dead(self) -> bool: # this considers maybe dead as dead
        self._auto_update_status()
        return True if self._status == HuntStatus.DEAD or self._status == HuntStatus.MAYBE_DEAD else False

    def is_maybe_dead(self) -> bool:
        self._auto_update_status()
        return True if self._status == HuntStatus.MAYBE_DEAD else False

    def is_found(self) -> bool:
        self._auto_update_status()
        return True if self._status == HuntStatus.FOUND else False

    def is_stale(self) -> bool:
        self._auto_update_status()
        return True if self._status == HuntStatus.UNKNOWN else False

    def get_status(self) -> str: # -> HuntStatus:
        self._auto_update_status()
        return self._status

    def get_status_str(self) -> str:
        status = self._status
        if status == HuntStatus.MAYBE_OPEN or status == HuntStatus.OPEN:
            return 'Open' # Hunt can spawn at anytime
        elif status == HuntStatus.FORCED:
            return 'Forced' # Hunt must be force spawned
        elif status == HuntStatus.FOUND:
            return 'Found' # Hunt is found
        elif status == HuntStatus.MAYBE_DEAD:
            return 'Maybe dead' # Is probably dead
        elif status == HuntStatus.DEAD:
            return 'Dead' # Is dead
        else:
            return 'Unknown' # Huh? HuntStatus.UNKNOWN?

    def get_last_updated(self) -> float:
        return self._last_updated

    def get_last_updated_source(self) -> str:
        return self._source

    def get_last_updated_since(self) -> float:
        return time.time() - self._last_updated


    # Modifying functions
    def update_status(self, new_status: str, update_time: float = time.time(), source: str = "", found_x: typing.Optional[float] = None, found_y: typing.Optional[float] = None) -> bool:
        self._auto_update_status()

        # Sanity checks
        if update_time <= (self._update_time - TIME_TOLERANCE):
            # Update is in the past
            return False
        elif update_time > (time.time() + TIME_TOLERANCE):
            # Update is in the future
            return False

        # Initialize update variable to track if the hunt should be updated
        update = False

        # Get a snapshot of the old status
        old_status = self._status

        # If no information is available
        if old_status == HuntStatus.UNKNOWN:
            # Ensure is a valid status (1 of 2)
            if new_status == HuntStatus.MAYBE_OPEN or new_status == HuntStatus.OPEN or new_status == HuntStatus.FORCED:
                update = True
            # Ensure is a valid status (2 of 2)
            elif new_status == HuntStatus.FOUND or new_status == HuntStatus.MAYBE_DEAD or new_status == HuntStatus.DEAD:
                update = True

        # If hunt is open, maybe open or forced
        elif old_status == HuntStatus.MAYBE_OPEN or old_status == HuntStatus.OPEN or HuntStatus.FORCED:
            # Hunt is found
            if new_status == HuntStatus.FOUND:
                update = True
            # Hunt is killed
            elif new_status == HuntStatus.DEAD:
                update = True
            # Hunt is probably killed
            elif new_status == HuntStatus.MAYBE_DEAD:
                update = True

        # If hunt is found
        elif old_status == HuntStatus.FOUND:
            # Hunt is killed
            if new_status == HuntStatus.DEAD:
                update = True
            # Hunt is probably killed
            elif new_status == HuntStatus.MAYBE_DEAD:
                update = True

        # If hunt is probably dead
        elif old_status == HuntStatus.MAYBE_DEAD:
            # Hunt is confirmed dead
            if new_status == HuntStatus.DEAD:
                update = True

        # If the hunt should be updated
        if update == True:
            self._status = new_status
            self._time_since_previous_update = update_time - self._last_updated
            self._last_updated = update_time
            self._source = source

            if (found_x is not None) and (found_y is not None):
                self._coords_x = found_x
                self._coords_y = found_y

        # Return if an update was performed
        # NOTE: The above could probably be optimized
        return update

    def force_update_status(self, new_status: str, update_time: float, source: str) -> bool:
        self._status = HuntStatus.UNKNOWN
        self._last_updated = update_time
        self._source = source
        return self.update_status(new_status, update_time, source)

    def reset(self, source: str) -> bool:
        self._status = HuntStatus.UNKNOWN
        self._last_updated = time.time()
        self._source = source
        return True
