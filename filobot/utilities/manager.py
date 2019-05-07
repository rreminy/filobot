import json
import logging
import os
import sys

import typing
from discord.ext.commands import Bot

from filobot.utilities.horus import HorusHunt
from .xivhunt import XivHunt
from .horus import Horus


class HuntManager:

    SUB_SB_A    = 'stormblood_a'
    SUB_SB_S    = 'stormblood_s'
    SUB_HW_A    = 'heavensward_a'
    SUB_HW_S    = 'heavensward_s'
    SUB_ARR_A   = 'a_realm_reborn_a'
    SUB_ARR_S   = 'a_realm_reborn_s'

    WORLDS = ['Any', 'Balmung', 'Brynhildr', 'Coeurl', 'Diabolos', 'Goblin', 'Malboro', 'Mateus', 'Zalera']

    def __init__(self, bot: Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

        self.xivhunt = XivHunt()
        self.horus = Horus()

        self._subscriptions = {}
        self._load_config()

        self._hunts = {}
        self._changed = {}
        self._found = {}
        self.recheck()

    def get(self, world: str, hunt_name: str) -> typing.Tuple[HorusHunt, dict]:
        xivhunt = self._hunts[world]['xivhunt'][hunt_name]
        horus   = self._hunts[world]['horus'][hunt_name]

        return horus, xivhunt

    def recheck(self):
        for world in self.WORLDS:
            if world == 'Any':
                continue

            if world not in self._hunts:
                self._hunts[world] = {'horus': {}, 'xivhunt': []}

            self._changed[world] = {}
            self._found[world] = {}

            xivhunt = self.xivhunt.load(world)
            horus   = self.horus.load(world)

            # Look for updated Horus entries
            for name, hunt in horus.items():  # type: str, HorusHunt
                if name in self._hunts[world]['horus'] and hunt.status != self._hunts[world]['horus'][name].status:
                    self._changed[world][name] = hunt

            # Check and see if hunts have been found on XIVHunt
            for name, hunt in xivhunt.items():  # type: str, dict
                if name in self._hunts[world]['xivhunt'] and hunt['status'] == 'seen':
                    # First time seeing this hunt?
                    if self._hunts[world]['xivhunt'][name]['status'] != 'seen':
                        self._log.info(f"""Hunt seen for the first time! {hunt['name']} on {world}""")
                        self._found[world][name] = hunt

            self._hunts[world]['xivhunt'] = xivhunt
            self._hunts[world]['horus']   = horus

    def subscribe(self, channel: int, world: str, subscription: str):
        if channel not in self._subscriptions:
            self._subscriptions[channel] = {}

        if world not in self._subscriptions[channel]:
            self._subscriptions[channel][world] = []

        sub = getattr(self, f"""SUB_{subscription.upper()}""")
        if sub is None:
            self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: sb_a, sb_s, hw_a, hw_s, arr_a, arr_s"
            )
            return

        if sub in self._subscriptions[channel][world]:
            self.bot.get_channel(channel).send(
                "This channel is already subscribed to this feed. If you want unsubscribe, use the unsub command"
            )
            return

        self._subscriptions[channel][world].append(sub)
        self.bot.get_channel(channel).send(f"""Subscribed channel to {str(sub).replace('_', ' ').title()} hunts""")
        self._save_config()

    def unsubscribe(self, channel: int, world: str, subscription: str):
        if channel not in self._subscriptions or world not in self._subscriptions[channel]:
            self.bot.get_channel(channel).send(
                "No subscriptions have been specified for this channel"
            )
            return

        sub = getattr(self, f"""SUB_{subscription.upper()}""")
        if sub is None:
            self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: sb_a, sb_s, hw_a, hw_s, arr_a, arr_s"
            )
            return

        if sub not in self._subscriptions[channel][world]:
            self.bot.get_channel(channel).send(
                "This channel is not subscribed to that feed"
            )
            return

    def _load_config(self):
        pass
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'subscriptions.json')) as json_file:
            self._subscriptions = json.load(json_file)

    def _save_config(self):
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'subscriptions.json')) as json_file:
            json_file.write(json.dumps(self._subscriptions))
