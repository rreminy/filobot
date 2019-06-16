import json
import logging
import os
import sys
import typing
import arrow
import discord

from discord.ext.commands import Bot
from filobot.utilities import hunt_embed
from filobot.utilities.horus import HorusHunt
from filobot.models import Subscriptions, SubscriptionsMeta, KillLog
from peewee import fn
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

    WORLDS = ('Balmung', 'Brynhildr', 'Coeurl', 'Diabolos', 'Goblin', 'Malboro', 'Mateus', 'Zalera')

    COND_DEAD = 'deaths'
    COND_OPEN = 'openings'
    COND_FIND = 'finds'
    CONDITIONS = (COND_DEAD, COND_OPEN, COND_FIND)

    def __init__(self, bot: Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

        self.xivhunt = XivHunt(bot)
        self.horus = Horus(bot)

        self._subscriptions = list(Subscriptions.select())
        self._subscriptions_meta = list(SubscriptionsMeta.select())

        self._marks_info = {}
        self._load_marks()

        self._hunts = {}
        self._changed = {}
        self._found = {}

        # Callbacks
        self._recheck_cbs = []

        # Logged notifications for editing later
        self._notifications = {}

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
            if world not in self._hunts:
                self._hunts[world] = {'horus': {}, 'xivhunt': []}

            self._changed[world] = {}
            self._found[world] = {}

            xivhunt = await self.xivhunt.load(world)
            horus   = await self.horus.load(world)

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
                        await self.on_find(world, name, hunt)

            self._hunts[world]['xivhunt'] = xivhunt
            self._hunts[world]['horus']   = horus
            await self.on_recheck(world, horus, xivhunt)

    async def on_recheck(self, world: str, horus: HorusHunt, xivhunt: dict):
        for callback in self._recheck_cbs:
            await callback(world, horus, xivhunt)

    def add_recheck_cb(self, callback: typing.Callable):
        if callback in self._recheck_cbs:
            self._log.warning('Callback already defined: ' + repr(callback))
            return

        self._recheck_cbs.append(callback)

    async def set_notifier(self, channel: int, role: discord.Role) -> None:
        """
        Set channel notifier
        """
        # Init our channel/world if needed
        SubscriptionsMeta.delete().where(
                (SubscriptionsMeta.channel_id == channel)
                & (SubscriptionsMeta.name == 'notifier')
        ).execute()
        SubscriptionsMeta.insert({
            'channel_id': channel,
            'name'      : 'notifier',
            'value'     : role.mention
        }).execute()

        self._reload()

    async def remove_notifier(self, channel: int) -> None:
        """
        Remove notifier from channel
        """
        SubscriptionsMeta.delete().where(
                (SubscriptionsMeta.channel_id == channel)
                & (SubscriptionsMeta.name == 'notifier')
        ).execute()

        self._reload()

    async def subscribe(self, channel: int, world: str, subscription: str, conditions: typing.Optional[str] = 'all'):
        """
        Subscribe a channel to hunt events
        """
        # Validate world
        world = world.strip().lower().title()
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

        # Already subscribed?
        if Subscriptions.select().where(
                (Subscriptions.channel_id == channel)
                & (Subscriptions.world == world)
                & (Subscriptions.category == sub)
        ).count():
            await self.bot.get_channel(channel).send(
                "This channel is already subscribed to this feed. If you want unsubscribe, use the unsub command"
            )
            return

        for condition in conditions:
            Subscriptions.insert({
                'channel_id': channel,
                'world'     : world,
                'category'  : sub,
                'event'     : condition
            }).execute()

        await self.bot.get_channel(channel).send(f"""Subscribed channel to {str(sub).replace('_', ' ').title()}-Rank hunts on {world}""")
        self._reload()

    async def subscribe_all(self, channel: int, subscription: str, conditions: typing.Optional[str] = 'all'):
        """
        Subscribe a channel to hunt events on all worlds
        """
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

        for world in self.WORLDS:
            # Already subscribed? Overwrite it
            Subscriptions.delete().where(
                    (Subscriptions.channel_id == channel)
                    & (Subscriptions.world == world)
                    & (Subscriptions.category == sub)
            )

            for condition in conditions:
                Subscriptions.insert({
                    'channel_id': channel,
                    'world'     : world,
                    'category'  : sub,
                    'event'     : condition
                }).execute()

        await self.bot.get_channel(channel).send(
            f"""Subscribed channel to {str(sub).replace('_', ' ').title()}-Rank hunts on **all worlds**"""
        )
        self._reload()

    async def unsubscribe(self, channel: int, world: str, subscription: str):
        """
        Unsubscribe a channel from hunt events
        """
        world = world.strip().lower().title()
        if world not in self.WORLDS:
            await self.bot.get_channel(channel).send(
                "No world by that name found on the Crystal DC - please check your spelling and try again"
            )
            return

        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            await self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: sb_a, sb_s, hw_a, hw_s, arr_a, arr_s"
            )
            return

        Subscriptions.delete().where(
                (Subscriptions.channel_id == channel)
                & (Subscriptions.world == world)
                & (Subscriptions.category == sub)
        ).execute()

        await self.bot.get_channel(channel).send(f"""Unsubscribed channel from {str(sub).replace('_', ' ').title()}-Rank hunts on {world}""")
        self._reload()

    async def get_subscriptions(self, channel: int) -> typing.List[Subscriptions]:
        """
        Get all subscriptions for the specified channel
        """
        return list(Subscriptions.select().where(Subscriptions.channel_id == channel))

    async def clear_subscriptions(self, channel: int) -> None:
        """
        Clear all subscriptions for the specified channel
        """
        Subscriptions.delete().where(Subscriptions.channel_id == channel).execute()
        self._reload()

    async def count(self) -> typing.Tuple[int, int]:
        """
        Return the total number of A-Ranks and S-Ranks relayed by Filo
        """
        a_count = list(SubscriptionsMeta.select(fn.SUM(SubscriptionsMeta.value).alias('total')).where(SubscriptionsMeta.name == 'a_count'))[0].total or 0
        s_count = list(SubscriptionsMeta.select(fn.SUM(SubscriptionsMeta.value).alias('total')).where(SubscriptionsMeta.name == 's_count'))[0].total or 0

        return (a_count, s_count)

    async def on_change(self, world: str, old: HorusHunt, new: HorusHunt):
        """
        Hunt status change event handler
        """
        hunt = self._marks_info[old.name.lower()]
        subs = Subscriptions.select().where(
                (Subscriptions.world == world)
                & (Subscriptions.category == hunt['Channel'])
        )
        embed = hunt_embed(new.name, new)

        for sub in subs:  # type: Subscriptions
            if new.status == new.STATUS_OPENED and self.COND_OPEN == sub.event:
                await self.bot.get_channel(sub.channel_id).send(f"""A hunt has opened on **{world}**!""", embed=embed)
                break

            if new.status == new.STATUS_MAXED and self.COND_OPEN == sub.event:
                await self.bot.get_channel(sub.channel_id).send(
                    f"""A hunts maximum spawn window has been reached on **{world}**!""", embed=embed)
                break

            if new.status == new.STATUS_DIED and self.COND_DEAD == sub.event:
                # If we previously sent a notification that the hunt was found, edit that message instead of
                # sending a new one
                notification = await self.get_notification(sub.channel_id, world, new.name)
                if notification:
                    notification, log = notification
                    found   = int(notification.created_at.timestamp())
                    killed  = arrow.get(int(new.last_mark / 1000)).timestamp
                    seconds = killed - log.found

                    kill_time = []
                    if seconds > 120:
                        kill_time.append(f"""{int(seconds / 60)} minutes""")
                        seconds -= int(seconds / 60) * 60
                    elif seconds > 60:
                        kill_time.append(f"""1 minute""")
                        seconds -= 60
                    kill_time.append(f"""{int(seconds)} seconds""")

                    log.killed = killed
                    log.kill_time = seconds
                    log.save()

                    await notification.edit(content=f"""A scouted hunt has died on **{world}** after **{', '.join(kill_time)}**!""", embed=embed)
                    break

                await self.bot.get_channel(sub.channel_id).send(f"""A hunt has died on **{world}**!""", embed=embed)
                break

    async def on_find(self, world: str, name: str, xivhunt: dict):
        """
        Hunt found event handler
        """
        hunt = self._marks_info[name.lower()]
        if hunt['Rank'] not in ('A', 'S'):
            self._log.debug(f"""Ignoring notifications for {hunt['Rank']} rank hunts""")
            return

        subs = Subscriptions.select().where(
                (Subscriptions.world == world)
                & (Subscriptions.category == hunt['Channel'])
        )
        embed = hunt_embed(name, xivhunt=xivhunt)

        for sub in subs:  # type: Subscriptions
            if self.COND_FIND != sub.event:
                continue

            _meta = SubscriptionsMeta.select().where(SubscriptionsMeta.channel_id == sub.channel_id)
            meta  = {m.name : m.value for m in _meta}
            role_mention = meta['notifier'] if 'notifier' in meta else None

            content = f"""A hunt has been found on **{world}**!"""
            if role_mention:
                content = f"""{role_mention} {content}"""
            message = await self.bot.get_channel(sub.channel_id).send(content, embed=embed)
            await self.log_notification(message, sub.channel_id, world, name)

            # Relay counter
            _counter_key = f"""{hunt['Rank'].lower()}_count"""
            if _counter_key not in meta:
                SubscriptionsMeta.insert({
                    'channel_id'    : sub.channel_id,
                    'name'          : _counter_key,
                    'value'         : 1
                }).execute()
            else:
                SubscriptionsMeta.update({
                    'value'         : int(meta[_counter_key]) + 1
                }).where(
                    (SubscriptionsMeta.channel_id == sub.channel_id)
                    & (SubscriptionsMeta.name == _counter_key)
                ).execute()
            break

    async def log_notification(self, message: discord.Message, channel: int, world: str, hunt_name: str) -> None:
        """
        Log a hunt found notification for editing later
        """
        hunt_name = hunt_name.lower()
        if channel not in self._notifications:
            self._notifications[channel] = {}
        if world not in self._notifications[channel]:
            self._notifications[channel][world] = {}

        log = KillLog.create(hunt_name=hunt_name, world=world, found=arrow.utcnow().timestamp)
        self._notifications[channel][world][hunt_name] = (message, log)
        self._log.debug("Notification message logged: " + repr(message))

    async def get_notification(self, channel: int, world: str, hunt_name: str) -> typing.Optional[typing.Tuple[discord.Message, KillLog]]:
        """
        Attempt to retrieve a notification message for a previously located hunt
        NOTE: Notifications are automatically purged after retrieved using this method
        """
        hunt_name = hunt_name.lower()
        if channel not in self._notifications or world not in self._notifications[channel]:
            return None

        if hunt_name in self._notifications[channel][world]:
            message, log = self._notifications[channel][world][hunt_name]
            del self._notifications[channel][world][hunt_name]
            return message, log

    def _reload(self):
        """
        Save configuration changes
        """
        self._subscriptions = list(Subscriptions.select())
        self._subscriptions_meta = list(SubscriptionsMeta.select())

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
