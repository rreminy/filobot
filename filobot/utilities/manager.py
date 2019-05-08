import json
import logging
import os
import sys
import typing
import yaml

from discord.ext.commands import Bot

from filobot.utilities import hunt_embed
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

    ARR_ZONES = ('Central Shroud', 'East Shroud', 'South Shroud', 'North Shroud', 'Western Thanalan',
                 'Central Thanalan', 'Eastern Thanalan', 'Southern Thanalan', 'Northern Thanalan', 'Middle La Noscea',
                 'Lower La Noscea', 'Eastern La Noscea', 'Western La Noscea', 'Upper La Noscea', 'Outer La Noscea',
                 'Mor Dhona')

    HW_ZONES = ('Coerthas Central Highlands', 'Coerthas Western Highlands', 'The Dravanian Forelands',
                'The Dravanian Hinterlands', 'The Churning Mists', 'The Sea of Clouds', 'Azys Lla')

    SB_ZONES = ('The Ruby Sea', 'Yanxia', 'The Azim Steppe', 'The Fringes', 'The Peaks', 'The Lochs')

    WORLDS = ('Any', 'Balmung', 'Brynhildr', 'Coeurl', 'Diabolos', 'Goblin', 'Malboro', 'Mateus', 'Zalera')

    COND_DEAD = 'deaths'
    COND_OPEN = 'openings'
    COND_FIND = 'finds'
    CONDITIONS = (COND_DEAD, COND_OPEN, COND_FIND)

    def __init__(self, bot: Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

        self.xivhunt = XivHunt()
        self.horus = Horus()

        self._subscriptions = {}
        self._load_config()

        self._marks_info = {}
        self._load_marks()

        self._hunts = {}
        self._changed = {}
        self._found = {}

    def get(self, world: str, hunt_name: str) -> typing.Tuple[HorusHunt, dict]:
        """
        Get data on the requested hunt
        """
        xivhunt = self._hunts[world]['xivhunt'][hunt_name]
        horus   = self._hunts[world]['horus'][hunt_name]

        return horus, xivhunt

    async def recheck(self):
        """
        Check and update hunt data from XIVHunt and Horus
        Calls on_change and on_find events respectively
        """
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
                    print(f"""Hunt status for {hunt.name} on {world} changed - {self._hunts[world]['horus'][name].status.title()} => {hunt.status.title()}""")
                    self._changed[world][name] = hunt
                    await self.on_change(world, self._hunts[world]['horus'][name], hunt)

            # Check and see if hunts have been found on XIVHunt
            for name, hunt in xivhunt.items():  # type: str, dict
                if name in self._hunts[world]['xivhunt'] and hunt['status'] == 'seen':
                    # First time seeing this hunt?
                    if self._hunts[world]['xivhunt'][name]['status'] != 'seen':
                        print(f"""Hunt seen for the first time! {name.title()} on {world}""")
                        self._found[world][name] = hunt
                        await self.on_find(world, hunt)

            self._hunts[world]['xivhunt'] = xivhunt
            self._hunts[world]['horus']   = horus

    async def subscribe(self, channel: int, world: str, subscription: str, conditions: typing.Optional[str] = 'all'):
        """
        Subscribe a channel to hunt events
        """
        # Validate world
        world = world.lstrip().rstrip().lower().title()
        if world not in self.WORLDS:
            await self.bot.get_channel(channel).send(
                "No world by that name found on the Crystal DC - please check your spelling and try again"
            )
            return

        # Validate subscription channel
        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            await self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: sb_a, sb_s, hw_a, hw_s, arr_a, arr_s"
            )
            return

        # Validate conditions
        if conditions == 'all':
            conditions = list(self.CONDITIONS)
        else:
            conditions = conditions.replace(' ', '').split(',')
            _invalid_conditions = set(conditions) - set(self.CONDITIONS)
            if _invalid_conditions:
                await self.bot.get_channel(channel).send(
                        "Invalid conditions supplied: " + str(_invalid_conditions)
                )
                return

        # Init our channel/world if needed
        if channel not in self._subscriptions:
            self._subscriptions[channel] = {}

        if world not in self._subscriptions[channel]:
            self._subscriptions[channel][world] = {}

        # Already subscribed?
        if sub in self._subscriptions[channel][world]:
            await self.bot.get_channel(channel).send(
                "This channel is already subscribed to this feed. If you want unsubscribe, use the unsub command"
            )
            return

        self._subscriptions[channel][world][sub] = conditions
        await self.bot.get_channel(channel).send(f"""Subscribed channel to {str(sub).replace('_', ' ').title()}-Rank hunts on {world}""")
        self._save_config()

    async def unsubscribe(self, channel: int, world: str, subscription: str):
        """
        Unsubscribe a channel from hunt events
        """
        world = world.lstrip().rstrip().lower().title()
        if world not in self.WORLDS:
            await self.bot.get_channel(channel).send(
                "No world by that name found on the Crystal DC - please check your spelling and try again"
            )
            return

        if channel not in self._subscriptions or world not in self._subscriptions[channel]:
            await self.bot.get_channel(channel).send(
                "No subscriptions have been specified for this channel"
            )
            return

        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            await self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: sb_a, sb_s, hw_a, hw_s, arr_a, arr_s"
            )
            return

        if sub not in self._subscriptions[channel][world]:
            await self.bot.get_channel(channel).send(
                "This channel is not subscribed to that feed"
            )
            return

        del self._subscriptions[channel][world][sub]
        await self.bot.get_channel(channel).send(f"""Unsubscribed channel from {str(sub).replace('_', ' ').title()}-Rank hunts on {world}""")
        self._save_config()

    async def on_change(self, world: str, old: HorusHunt, new: HorusHunt):
        for channel_id, subs in self._subscriptions.items():
            for _world, sub in subs.items():
                if _world != world:
                    continue

                hunt = self._marks_info[old.name.lower()]
                if hunt['Channel'] in sub:
                    sub_conditions = sub[hunt['Channel']]
                    embed = hunt_embed(new.name, new)

                    if new.status == new.STATUS_OPENED and self.COND_OPEN in sub_conditions:
                        await self.bot.get_channel(channel_id).send("A hunt has opened!", embed=embed)
                        break

                    if new.status == new.STATUS_MAXED and self.COND_OPEN in sub_conditions:
                        await self.bot.get_channel(channel_id).send("A hunts maximum spawn window has been reached!", embed=embed)
                        break

                    if new.status == new.STATUS_DIED and self.COND_DEAD in sub_conditions:
                        await self.bot.get_channel(channel_id).send("A hunt has died!", embed=embed)
                        break

    async def on_find(self, world: str, hunt: dict):
        pass

    def _load_config(self):
        """
        Load saved configuration
        """
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'subscriptions.yaml')) as cf:
            self._subscriptions = yaml.load(cf) or {}

        self._log.info('Subscriptions loaded: ' + str(self._subscriptions))

    def _save_config(self):
        """
        Save configuration changes
        """
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'subscriptions.yaml'), 'w') as cf:
            cf.write(yaml.dump(self._subscriptions))

    def _load_marks(self):
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json')) as json_file:
            marks = json.load(json_file)

            for _id, mark in marks.items():
                key = mark['Name'].lower()
                self._marks_info[key] = mark

                if mark['ZoneName'] in self.ARR_ZONES and (mark['Rank'] == 'A' or mark['Rank'] == 'S'):
                    channel = getattr(self, f"""SUB_ARR_{mark['Rank']}""")
                    self._marks_info[key]['Channel'] = channel
                elif mark['ZoneName'] in self.HW_ZONES and (mark['Rank'] == 'A' or mark['Rank'] == 'S'):
                    channel = getattr(self, f"""SUB_HW_{mark['Rank']}""")
                    self._marks_info[key]['Channel'] = channel
                elif mark['ZoneName'] in self.SB_ZONES and (mark['Rank'] == 'A' or mark['Rank'] == 'S'):
                    channel = getattr(self, f"""SUB_SB_{mark['Rank']}""")
                    self._marks_info[key]['Channel'] = channel
                else:
                    self._log.info(f"""Not binding hunt {mark['Name']} to a subscription channel""")
