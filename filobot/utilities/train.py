import datetime
import logging
import typing
import discord

from filobot.utilities import parse_duration_string
from filobot.utilities.horus import HorusHunt
from filobot.utilities.manager import HuntManager


class Conductor:

    def __init__(self, hunt_manager: HuntManager, world: str, starting_target: typing.Optional[str] = None):
        self._hunt_manager = hunt_manager
        self._log = logging.getLogger(__name__)

        self.world = world.strip().lower().title()
        self._hunts = [
            self._hunt_manager.get(self.world, 'erle'),
            self._hunt_manager.get(self.world, 'orcus'),
            self._hunt_manager.get(self.world, 'vochstein'),
            self._hunt_manager.get(self.world, 'aqrabuamelu'),
            self._hunt_manager.get(self.world, 'mahisha'),
            self._hunt_manager.get(self.world, 'luminare'),
            self._hunt_manager.get(self.world, 'funa yurei'),
            self._hunt_manager.get(self.world, 'oni yumemi'),
            self._hunt_manager.get(self.world, 'gajasura'),
            self._hunt_manager.get(self.world, 'angada'),
            self._hunt_manager.get(self.world, 'girimekhala'),
            self._hunt_manager.get(self.world, 'sum')
        ]
        self._first = self._hunt_manager.get(self.world, starting_target)[0] if starting_target else self._hunts[0][0]
        # self._hunts = list(filter(lambda h: h[0].status != h[0].STATUS_DIED, self._hunts))
        self._previous = None  # type: typing.Optional[HorusHunt]
        self._next = []  # type: typing.List[str]

        self.started = datetime.datetime.utcnow()
        self.total = len(self._hunts)
        self.finished = False

    def hunt_is_in_train(self, hunt_name: str):
        hunt_name = hunt_name.strip().lower()
        for horushunt, xivhunt in self._hunts:
            if horushunt.name.lower() == hunt_name:
                return True

        return False

    def log_kill(self, hunt_name: str):
        for index, hunt_data in enumerate(self._hunts):
            horushunt, xivhunt = hunt_data
            if horushunt.name.lower() == hunt_name:
                self._previous = horushunt

                # Figure out our most likely next hunt target(s)
                next_hunts = []
                previous_insert = None  # type: typing.Optional[HorusHunt]
                try:
                    next_hunts.append(self._parse_location(*self._hunts[index + 1]))
                    previous_insert = self._hunts[index + 1][0]
                except IndexError:
                    if self._hunts and len(self._hunts) > 1:
                        next_hunts.append(self._parse_location(*self._hunts[0]))
                    else:
                        self.finished = True

                if not self.finished:
                    for horushunt, xivhunt in self._hunts:
                        if (horushunt.zone == self._previous.zone) and (horushunt.name != self._previous.name):
                            if previous_insert and (previous_insert.name != horushunt.name):
                                next_hunts.insert(0, self._parse_location(horushunt, xivhunt))
                                break
                    else:
                        try:
                            alt_next = self._hunts[index + 2]
                            next_hunts.append(self._parse_location(*alt_next))
                        except IndexError:
                            pass

                self._next = next_hunts
                del self._hunts[index]
                break
        else:
            self._log.warning(f'Attempted to log a kill for hunt target {hunt_name}, but it was not found')

    def _embed(self, hunt: HorusHunt) -> discord.Embed:
        embed = discord.Embed(title='Stormblood Hunt Train', description=f"**{self.world}**")
        embed.set_thumbnail(url=hunt.image)
        embed.colour = 0x7CB518

        if self._previous:
            embed.add_field(name='Previous target', value=self._previous.name)
        else:
            embed.add_field(name='Starting target', value=self._first.name)

        if self._next:
            embed.add_field(name='Next targets', value="\n".join(self._next))

        kill_count = self.total - len(self)
        percentage = round((kill_count / self.total) * 100) if kill_count else 0
        embed.add_field(name='Progress', value=f"{kill_count} / {self.total} ({percentage}%)")

        embed.set_footer(text='Last updated')
        embed.timestamp = datetime.datetime.utcnow()

        return embed

    def _parse_location(self, horushunt, xivhunt):
        if xivhunt['coords']:
            return f"{horushunt.name} • {horushunt.zone} • ({xivhunt['coords']})"

        return f"{horushunt.name} • ({horushunt.zone})"

    def __next__(self):
        if self._previous is None:
            return self._embed(self._first)

        if self.finished:
            embed = discord.Embed(title='Stormblood Hunt Train', description=f"**{self.world}**")
            embed.colour = 0xFB6107
            # embed.add_field(name='Status', value='Completed')
            embed.add_field(name='Duration', value=parse_duration_string(self.started.timestamp(), datetime.datetime.utcnow().timestamp()))
            embed.set_footer(text='Completion date')
            embed.timestamp = datetime.datetime.utcnow()

            return embed

        return self._embed(self._previous)

    def __len__(self):
        return len(self._hunts)
