import json
import logging
import os
import sys
import typing
import time
import datetime
import asyncio

import arrow
import discord
from discord.ext.commands import Bot
from peewee import fn

from filobot.models import KillLog, Subscriptions, SubscriptionsMeta
from filobot.utilities import hunt_simple_embed, fate_simple_embed
from filobot.utilities.horus import HorusHunt
from .horus import Horus
from .xivhunt import XivHunt
from filobot.utilities.worlds import Worlds
from filobot.utilities.time_utils import RemainingTime


class HuntManager:

    JA_DATACENTERS = ['Elemental', 'Gaia', 'Mana', 'Meteor']
    EU_DATACENTERS = ['Light', 'Chaos']
    NA_DATACENTERS = ['Primal', 'Aether', 'Crystal', 'Dynamis']
    OC_DATACENTERS = ['Materia']

    SUB_DT_A    = 'dawntrail_a'
    SUB_DT_S    = 'dawntrail_s'
    SUB_EW_A    = 'endwalker_a'
    SUB_EW_S    = 'endwalker_s'
    SUB_SHB_A   = 'shadowbringers_a'
    SUB_SHB_S   = 'shadowbringers_s'
    SUB_SB_A    = 'stormblood_a'
    SUB_SB_S    = 'stormblood_s'
    SUB_HW_A    = 'heavensward_a'
    SUB_HW_S    = 'heavensward_s'
    SUB_ARR_A   = 'a_realm_reborn_a'
    SUB_ARR_S   = 'a_realm_reborn_s'
    SUB_FATE    = 'rare_fates'
    SUB_TRAINS  = 'trains'

    HUNT_SUBSCRIPTIONS = ('dt_a', 'dt_s', 'ew_a', 'ew_s', 'shb_a', 'shb_s', 'sb_a', 'sb_s', 'hw_a', 'hw_s', 'arr_a', 'arr_s')

    ARR_ZONES = ('Central Shroud', 'East Shroud', 'South Shroud', 'North Shroud', 'Western Thanalan',
                 'Central Thanalan', 'Eastern Thanalan', 'Southern Thanalan', 'Northern Thanalan', 'Middle La Noscea',
                 'Lower La Noscea', 'Eastern La Noscea', 'Western La Noscea', 'Upper La Noscea', 'Outer La Noscea',
                 'Mor Dhona', 'Coerthas Central Highlands')

    HW_ZONES = ('Coerthas Western Highlands', 'The Dravanian Forelands', 'The Dravanian Hinterlands', 'The Churning Mists', 'The Sea of Clouds', 'Azys Lla')

    SB_ZONES = ('The Ruby Sea', 'Yanxia', 'The Azim Steppe', 'The Fringes', 'The Peaks', 'The Lochs')

    SHB_ZONES = ('Il Mheg', "The Rak'tika Greatwood", 'The Tempest', 'Amh Araeng', 'Lakeland', 'Kholusia')

    EW_ZONES = ('Labyrinthos', "Thavnair", 'Garlemald', 'Mare Lamentorum', 'Elpis', 'Ultima Thule')

    DT_ZONES = ("Kozama'uka", "Yak T'el", "Urqopacha", "Shaaloani", "Heritage Found", "Living Memory")

    COND_DEAD = 'deaths'
    COND_OPEN = 'openings'
    COND_FIND = 'finds'
    CONDITIONS = (COND_DEAD, COND_OPEN, COND_FIND)

    lock = asyncio.Lock()

    def __init__(self, bot: Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

        self.xivhunt = XivHunt(bot)
        self.horus = Horus(bot)

        self._subscriptions = list(Subscriptions.select())
        self._subscriptions_meta = list(SubscriptionsMeta.select())

        self._marks_info = {}
        self._fates_info = {}
        self._achievementfates_info = {}
        self._zones_info = {}
        self._load_marks()
        self._load_fates()
        self._load_zones()

        self._hunts = {}
        self._changed = {}
        self._found = {}
        self._timers = {}
        self._fate_timers = {}

        self._recent_fates = {}

        # Callbacks
        self._recheck_cbs = []

        # Logged notifications for editing later
        self._notifications = {}

        # Minions tracker
        self.minions = dict()

    def get(self, world: str, hunt_name: str, instance=1) -> HorusHunt:
        """
        Get data on the requested hunt
        """
        _key = f"{hunt_name.lower().strip()}_{instance}"
        return self._hunts[world]['horus'][_key]

    def getExpansion(self, name: dict) -> str:
        zone_id = int(name['ZoneID'])

        if zone_id < 211:
            return "arr"
        elif zone_id < 354:
            return "hw"
        elif zone_id < 494:
            return "sb"
        elif zone_id < 956:
            return "shb"
        elif zone_id < 962:
            return "ew"
        else:
            return "dt"

    async def recheck(self):
        """
        Check and update hunt data from XIVHunt and Horus
        Calls on_change and on_find events respectively
        """
        # Update Horus
        await self.horus.update_horus()

        for world in Worlds.get_worlds():
            if world not in self._hunts:
                self._hunts[world] = {'horus': {}, 'xivhunt': []}

            self._changed[world] = {}
            self._found[world] = {}

            # xivhunt = await self.xivhunt.load(world)
            horus   = await self.horus.load(world)
            if horus is None:
                continue

            # Look for updated Horus entries
            job_list = list()
            for key, hunt in horus.items():  # type: str, HorusHunt
                if key in self._hunts[world]['horus'] and hunt.status != self._hunts[world]['horus'][key].status:
                    self._log.info(f"""Hunt status for {hunt.name} on {world} (Instance {hunt.instance}) changed - {self._hunts[world]['horus'][key].status.title()} => {hunt.status.title()}""")
                    self._changed[world][key] = hunt
                    job_list.append(self.on_change(world, self._hunts[world]['horus'][key], hunt))
            await asyncio.gather(*job_list)

            # Check and see if hunts have been found on XIVHunt
            # for name, hunt in xivhunt.items():  # type: str, dict
            #     if name in self._hunts[world]['xivhunt'] and hunt['status'] == 'seen':
            #         # First time seeing this hunt?
            #         if self._hunts[world]['xivhunt'][name]['status'] != 'seen':
            #             self._log.info(f"""Hunt seen for the first time! {name.title()} on {world}""")
            #             self._found[world][name] = hunt
            #             await self.on_find(world, name, hunt)

            # self._hunts[world]['xivhunt'] = xivhunt
            self._hunts[world]['horus'] = horus
            await self.on_recheck(world, horus)

    async def recheck_trackers(self, source: str, name: str, hunt: HorusHunt, instance: int):
        """
        Acknowledge hunt data from Beartracker
        Calls on_change and on_find events respectively
        """
        world = hunt.world

        if world not in self._hunts:
            self._hunts[world] = {'horus': {}, 'xivhunt': []}

        self._changed[world] = {}
        self._found[world] = {}

        key = f"{name.strip().lower()}_{instance}"

        job_list = list()
        if key in self._hunts[world]['horus'] and hunt.status != self._hunts[world]['horus'][key].status and hunt.open_date > self._hunts[world]['horus'][key].open_date:
            self._log.info(f"""Hunt status for {name} on {world} (Instance {hunt.instance}) changed - {self._hunts[world]['horus'][key].status.title()} => {hunt.status.title()}""")
            self._changed[world][key] = hunt
            job_list.append(self.on_change(world, self._hunts[world]['horus'][key], hunt))
        await asyncio.gather(*job_list)

    async def on_recheck(self, world: str, horus: HorusHunt):
        for callback in self._recheck_cbs:
            await callback(world, horus)

    def add_recheck_cb(self, callback: typing.Callable):
        if callback in self._recheck_cbs:
            self._log.warning('Callback already defined: ' + repr(callback))
            return

        self._recheck_cbs.append(callback)

    async def check_fates(self):
        self._log.debug(f"""Checking FATES""")
        for world in self._recent_fates:
            for recent_fate, expired_time in self._recent_fates[world].items():
                time_distance = (int(time.time()) - expired_time)
                # self._log.debug(f"""recent_fate: {repr(recent_fate)}\nexpired_time: {repr(expired_time)}\ntime_distance: {repr(time_distance)}""")
                if time_distance >= 60 and time_distance < 180:
                    if recent_fate in self._hunts[world]['xivhunt']:
                        self._hunts[world]['xivhunt'].remove(recent_fate)

        async with self.lock:
            job_list = list()
            for channel in list(self._notifications.keys()):
                for world in list(self._notifications[channel].keys()):
                    for key in list(self._notifications[channel][world].keys()):
                        name = key.rsplit("_")[0]

                        if name in self._fates_info.keys() and self._notifications[channel][world][key]:
                            message, log = self._notifications[channel][world][key]
                            message = await message.fetch()
                            try:
                                embed = message.embeds[0]
                            except:
                                continue

                            if not embed:
                                continue

                            seconds_left = RemainingTime.from_simple_time(embed.footer.text if isinstance(embed.footer.text, str) else "30:00").to_seconds()
                            message_time = message.edited_at if message.edited_at is not None else message.created_at

                            self._log.info(f"""edited_at: {repr(message.edited_at)}\ncreated_at: {repr(message.created_at)}""")

                            if int(time.time()) >= int(message_time.timestamp()) + seconds_left:
                                #  Strikethrough the fate!
                                # self._log.info(f"""Expiring? Fate: {self._fates_info[name]['Name']} ({world})\n{time.time()} >= {int(message_time.replace(tzinfo=datetime.timezone.utc).timestamp())} + {seconds_left} ({int(message_time.replace(tzinfo=datetime.timezone.utc).timestamp()) + seconds_left})""")
                                job_list.append(self.on_progress(world, self._fates_info[name]['Name'], None, int(key.rsplit("_")[1])))
        await asyncio.gather(*job_list)

    async def set_notifier(self, channel: int, role: discord.Role, attachname: str) -> None:
        """
        Set channel notifier
        """

        # Init our channel/world if needed
        SubscriptionsMeta.delete().where(
                (SubscriptionsMeta.channel_id == channel)
                & (SubscriptionsMeta.name == 'notifier')
                & (SubscriptionsMeta.attachName == attachname)
        ).execute()
        SubscriptionsMeta.insert({
            'channel_id': channel,
            'attachName': attachname,
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
        Subscribe a channel to hunt and fate events
        """
        # Validate world
        world = world.strip().lower().title()
        if world not in Worlds.get_worlds():
            #await self.bot.get_channel(channel).send("No world by that name found - please check your spelling and try again", ephemeral=True)
            return "No world by that name found - please check your spelling and try again"

        # Validate subscription channel
        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            #await self.bot.get_channel(channel).send("Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains", ephemeral=True)
            return "Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"

        # Validate conditions
        if conditions == 'all':
            conditions = list(self.CONDITIONS)
        else:
            conditions = conditions.replace(' ', '').lower().split(',')
            _invalid_conditions = set(conditions) - set(self.CONDITIONS)
            if _invalid_conditions:
                #await self.bot.get_channel(channel).send("Invalid conditions supplied: " + str(_invalid_conditions))
                return ("Invalid conditions supplied: " + str(_invalid_conditions))

        # Already subscribed?
        if Subscriptions.select().where(
                (Subscriptions.channel_id == channel)
                & (Subscriptions.world == world)
                & (Subscriptions.category == sub)
        ).count():
            #await self.bot.get_channel(channel).send("This channel is already subscribed to this feed. If you want unsubscribe, use the unsub command", ephemeral=True)
            return "This channel is already subscribed to this feed. If you want unsubscribe, use the unsub command"

        for condition in conditions:
            Subscriptions.insert({
                'channel_id': channel,
                'world'     : world,
                'category'  : sub,
                'event'     : condition
            }).execute()

        #await self.bot.get_channel(channel).send(f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on {world}""", ephemeral=True)
        message = f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on {world}"""
        self._reload()
        return message

    async def subscribe_all(self, datacenter: str, channel: int, subscription: str, conditions: typing.Optional[str] = 'all'):
        """
        Subscribe a channel to hunt and fate events on all worlds
        """
        # Validate subscription channel
        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            #await self.bot.get_channel(channel).send("Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains", ephemeral=True)
            return "Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"

        # Validate conditions
        if conditions == 'all':
            conditions = list(self.CONDITIONS)
        else:
            conditions = conditions.replace(' ', '').lower().split(',')
            _invalid_conditions = set(conditions) - set(self.CONDITIONS)
            if _invalid_conditions:
                #await self.bot.get_channel(channel).send("Invalid conditions supplied: " + str(_invalid_conditions), ephemeral=True)
                return ("Invalid conditions supplied: " + str(_invalid_conditions))

        # Validate datacenter
        datacenter = datacenter.strip().lower().title()
        if datacenter not in Worlds.get_datacenters():
            #await self.bot.get_channel(channel).send(f"Invalid datacenter provided, valid datacenters are: {', '.join(Worlds.get_datacenters())}", ephemeral=True)
            return (f"Invalid datacenter provided, valid datacenters are: {', '.join(Worlds.get_datacenters())}")

        for world in Worlds.get_datacenter_worlds(datacenter):
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

        #await self.bot.get_channel(channel).send(f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on **all worlds**""", ephemeral=True)
        message = f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on **all worlds**"""
        self._reload()
        return message

    async def unsubscribe(self, channel: int, world: str, subscription: str):
        """
        Unsubscribe a channel from hunt and fate events
        """
        world = world.strip().lower().title()
        if world not in Worlds.get_worlds():
            #await self.bot.get_channel(channel).send("No world by that name found - please check your spelling and try again", ephemeral=True)
            return "No world by that name found - please check your spelling and try again"

        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            #await self.bot.get_channel(channel).send("Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains", ephemeral=True)
            return "Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"

        Subscriptions.delete().where(
                (Subscriptions.channel_id == channel)
                & (Subscriptions.world == world)
                & (Subscriptions.category == sub)
        ).execute()

        #await self.bot.get_channel(channel).send(f"""Unsubscribed channel from {str(sub).replace('_', ' ').title()} on {world}""", ephemeral=True)
        message = f"""Unsubscribed channel from {str(sub).replace('_', ' ').title()} on {world}"""
        self._reload()
        return message

    async def get_subscriptions(self, channel: int) -> typing.List[Subscriptions]:
        """
        Get all subscriptions for the specified channel
        """
        return list(Subscriptions.select().where(Subscriptions.channel_id == channel))

    async def get_subscriptionsmetas(self, channel: int) -> typing.List[Subscriptions]:
        """
        Get all subscriptions for the specified channel
        """
        return list(SubscriptionsMeta.select().where(SubscriptionsMeta.channel_id == channel))

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

    def get_killed_text(self, seconds, is_jp):
        return f"""**Killed {"殺された" if is_jp else ""}**""" #  *(after {RemainingTime(seconds).to_verbose()}{"後" if is_jp else ""})*

    def get_expired_text(self, seconds, is_jp):
        return f"""**Expired {"期限切れ" if is_jp else ""}**""" #  *(after {RemainingTime(seconds).to_verbose()}{"後" if is_jp else ""})*


    async def on_progress(self, world: str, name: str, xivhunt: dict, instance=1):
        """
        FATE progress event handler
        """

        _key = f"{name.strip().lower()}_{instance}"

        fate = self._fates_info[name.lower()]
        subs = Subscriptions.select().where(
                (Subscriptions.world == world)
                & (Subscriptions.category == fate['Channel'])
        )
        embed = fate_simple_embed(name, xivhunt)

        info = self._fates_info[name.lower()]

        for sub in subs:  # type: Subscriptions
            try:
                # If we previously sent a notification that the fate was found, edit that message instead of sending a new one
                notification = await self.get_notification(sub.channel_id, world, name, instance, False)

                if notification:
                    notification, log = notification
                    notification = await notification.fetch()

                    # Get the original content
                    content = notification.content

                    time_left = xivhunt['last_seen'] if xivhunt else 0

                    if (not time_left or int(xivhunt['status']) == 100) and self.COND_DEAD == sub.event:
                        killed  = notification.edited_at.replace(tzinfo=datetime.timezone.utc).timestamp() if not time_left and notification.edited_at is not None else int(time.time())
                        seconds = killed - log.found
                        ja_seconds = ""
                        ja_minutes = ""

                        if Worlds.get_world_datacenter(world) in self.JA_DATACENTERS:
                            ja_seconds, ja_minutes = "秒", "分"

                        kill_time = RemainingTime(seconds)

                        log.killed = killed
                        log.kill_time = seconds
                        log.save()

                        # Remove the ping mention
                        #beg = content.find(f"[{world}]")
                        #content = content[beg:]

                        is_jp = Worlds.get_world_datacenter(world) in self.JA_DATACENTERS

                        if time_left:
                            self._log.debug(f"FATE {name} on world {world} instance {instance} killed [1]\n{repr(xivhunt)}")
                            content = f"~~{content}~~ {self.get_killed_text(seconds, is_jp)}"
                        elif (xivhunt is not None and int(xivhunt['status']) > 0):
                            if notification.edited_at is not None and (time.time() - notification.edited_at.timestamp()) > 120:
                                self._log.debug(f"FATE {name} on world {world} instance {instance} killed [2]\n{repr(xivhunt)}")
                                content = f"~~{content}~~ {self.get_killed_text(seconds, is_jp)}"
                            else:
                                self._log.debug(f"FATE {name} on world {world} instance {instance} expired [1]\n{repr(xivhunt)}")
                                content = f"~~{content}~~ {self.get_expired_text(seconds, is_jp)}"
                        else:
                            self._log.debug(f"FATE {name} on world {world} instance {instance} expired [2]\n{repr(xivhunt)}")
                            content = f"~~{content}~~ {self.get_expired_text(seconds, is_jp)}"

                        if _key not in self._notifications[sub.channel_id][world]:
                            return

                        async with self.lock:
                            del self._notifications[sub.channel_id][world][_key]

                    # if not notification.author.bot:
                    #     continue

                    # Set embed description
                    embed = notification.embeds[0]

                    if xivhunt:
                        self._log.debug(f"FATE {name} on world {world} instance {instance} data\n{repr(xivhunt)}")
                        embed.description = embed.description[embed.description.find("%") + 1:]
                        embed.description = f"{xivhunt['status']}%{embed.description}"
                    if content[0] == "~":
                        embed.set_image(url=None)

                    if time_left >= 0:
                        remaining_str = RemainingTime(time_left).to_simple()
                        duration_str = ""
                        if (info['Duration'] > 0):
                            duration_str = f" / {RemainingTime(info['Duration']).to_simple()}"

                        if Worlds.get_world_datacenter(world) in self.JA_DATACENTERS:
                            embed.set_footer(text=f"""残り{remaining_str}{duration_str} remaining""")
                        elif Worlds.get_world_datacenter(world) in self.EU_DATACENTERS:
                            embed.set_footer(text=f"""{remaining_str}{duration_str} remaining / restant""")
                        else:
                            embed.set_footer(text=f"""{remaining_str}{duration_str} remaining""")

                    # Edit the message
                    await notification.edit(content=content, embed=embed)
                    #  await self.log_notification(notification, sub.channel_id, world, fate['Channel'], instance) #  I think this isn't needed and it'll break another thing
            except discord.NotFound:
                self._log.warning(f"Notification message for FATE {name} on world {world} has been deleted")

        time_left = xivhunt['last_seen'] if xivhunt else 0

        if (not time_left or int(xivhunt['status']) == 100):
            if _key in self._hunts[world]['xivhunt']:
                if world not in self._recent_fates:
                    self._recent_fates[world] = {}
                if _key not in self._recent_fates[world]:
                    self._recent_fates[world][_key] = int(time.time())

    async def on_change(self, world: str, old: HorusHunt, new: HorusHunt):
        """
        Hunt status change event handler
        """
        hunt = self._marks_info[old.name.lower()]
        if 'Channel' not in hunt:
            return
        try:
            subs = Subscriptions.select().where(
                    (Subscriptions.world == world)
                    & (Subscriptions.category == hunt['Channel'])
            )
            embed = hunt_simple_embed(new.name, new)
        except:
            # self._log.warning(f"""{hunt['Name']}""")
            # raise
            return

        for sub in subs:  # type: Subscriptions
            if new.status == new.STATUS_OPENED and self.COND_OPEN == sub.event:
                await self._send_sub_message(f"A hunt has opened on **{world}** (**Instance {new.instance}**)!", embed, sub)
                continue

            if new.status == new.STATUS_MAXED and self.COND_OPEN == sub.event:
                await self._send_sub_message(f"A hunts maximum spawn window has been reached on **{world}** (**Instance {new.instance}**)!", embed, sub)
                continue

            if new.status == new.STATUS_DIED and self.COND_DEAD == sub.event:
                # If we previously sent a notification that the hunt was found, edit that message instead of
                # sending a new one
                notification = await self.get_notification(sub.channel_id, world, new.name, new.instance)
                if notification:
                    notification, log = notification
                    killed  = arrow.get(int(new.last_mark / 1000)).timestamp()
                    seconds = killed - log.found
                    ja_seconds = ""
                    ja_minutes = ""

                    if Worlds.get_world_datacenter(world) in self.JA_DATACENTERS:
                        ja_seconds, ja_minutes = "秒", "分"

                    log.killed = killed
                    log.kill_time = seconds
                    log.save()

                    try:
                        if notification.author.bot:
                            # Get the original content
                            content = notification.content

                            # Remove the ping mention
                            #beg = content.find(f"[{new.world}]")
                            #content = content[beg:]

                            # Set embed description
                            try:
                                embed.description = f"~~{notification.embeds[0].description}~~" if notification.embeds[0].description else ""
                                embed.set_image(url=discord.Embed.Empty) # This might be giving a secret error, we may want to use None instead
                            except:
                                pass

                            # Add dead timing to message
                            content = f"~~{content}~~ {self.get_killed_text(seconds, Worlds.get_world_datacenter(world) in self.JA_DATACENTERS)}"

                            # Edit the message
                            await notification.edit(content=content, embed=embed)
                    except discord.NotFound:
                        self._log.warning(f"Notification message for hunt {new.name} on world {world} has been deleted")
                    except:
                        self._log.exception("Exception thrown");

            _key = f"{new.name.strip().lower()}_{new.instance}"
            if _key in self._hunts[world]['xivhunt']:
                self._hunts[world]['xivhunt'].remove(_key)

        # Check if all A ranks are dead yet so we can end the train
        if hunt['Rank'] == 'A' and hunt['ZoneName'] in self.EW_ZONES and self._hunts[world]['horus'] is not None and new.status == new.STATUS_DIED:
            hunts_living, previous_death = False, 0

            for key, horusHunt in self._hunts[world]['horus'].items():
                if horusHunt.rank == 'A' and horusHunt.zone in self.EW_ZONES and horusHunt.name != new.name:
                    if horusHunt.status != horusHunt.STATUS_DIED:
                        hunts_living = True
                    if horusHunt.status == horusHunt.STATUS_DIED and int(horusHunt.last_alive) / 1000 > previous_death:
                        previous_death = int(horusHunt.last_alive) / 1000

            if not hunts_living and int(time.time()) - (int(new.last_alive) / 1000) < 60:  # If last death report is retroactive, don't send a random "Complete" message
                # All A ranks are dead, alter the train message
                await self.on_train(world, new.name, None, True, new.instance)
                return

            if previous_death and int(int(new.last_alive) / 1000) == int(int(new.last_mark) / 1000): # Don't report a train if it's a retroactive mark
                time_between = (int(new.last_alive) / 1000) - previous_death

                if time_between > 40 and time_between < 240:  # More than 40 seconds, less than 4 minutes between deaths?
                    await self.on_train(world, new.name, None, False, new.instance)  # It's a train then


    async def on_train(self, world: str, name: str, xivhunt: dict, complete: bool, instance=1):
        """
        Train event handler
        """
        hunt = self._marks_info[name.lower()]

        subs = Subscriptions.select().where(
                (Subscriptions.world == world)
                & (Subscriptions.category == getattr(self, "SUB_TRAINS"))
        )

        instancesymbol = "①" if instance == 1 else "②" if instance == 2 else "③" if instance == 3 else instance

        for sub in subs:  # type: Subscriptions
            _meta = SubscriptionsMeta.select().where((SubscriptionsMeta.channel_id == sub.channel_id) & (SubscriptionsMeta.attachName == "trains"))
            meta  = {m.name : m.value for m in _meta}
            role_mention = meta['notifier'] if 'notifier' in meta else None

            if not complete:
                zone_name = f"""{hunt['ZoneName']} {self._zones_info[str(hunt['ZoneID'])]['name_ja']} """ if Worlds.get_world_datacenter(world) in self.JA_DATACENTERS else f"""{hunt['ZoneName']} """

                if xivhunt is not None:
                    content = f"""[{world}] {zone_name}({xivhunt['coords']}) {instancesymbol}"""
                else:
                    if self.COND_DEAD == sub.event:  # Announce train updates using only death reports!
                        content = f"""[{world}] {zone_name} {instancesymbol}"""
                    else:
                        continue

                if role_mention:
                    content = f"""{role_mention} {content}"""
            else:
                content = f"""[{world}]狩ツアコンプリートComplete""" if Worlds.get_world_datacenter(world) in self.JA_DATACENTERS else f"""[{world}] Complete"""

            # Attempt to edit an existing message first
            notification = await self.get_notification(sub.channel_id, world, self.SUB_TRAINS, 1, complete)

            if notification:
                notification, log = notification
                last_train_announcement = int(notification.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())

                if int(time.time()) - last_train_announcement < 7200: #  Last train announcement less than 2 hours ago? Edit it
                        try:
                            if notification.content != content:
                                await notification.edit(content=content) #  Edit the message
                                await self.log_notification(notification, sub.channel_id, world, self.SUB_TRAINS, 1)
                            continue
                        except discord.NotFound:
                            self._log.warning(f"Train announcement was deleted for {world}.")
                        except:
                            self._log.exception("Exception thrown")
                else:
                    if not complete and f"{self.SUB_TRAINS.lower()}_1" in self._notifications[sub.channel_id][world]:
                        async with self.lock:
                            del self._notifications[sub.channel_id][world][f"{self.SUB_TRAINS.lower()}_1"]

            if not complete or self.COND_DEAD == sub.event:
                # Sending a new message
                message = await self._send_sub_message(content, None, sub)

                if not message:
                    continue

                await self.log_notification(message, sub.channel_id, world, self.SUB_TRAINS, 1)

    async def on_find(self, world: str, name: str, xivhunt: dict, instance=1):
        """
        Hunt and fate found event handler
        """
        self._log.debug(f"on_find: World = {world} | name = {name} | xivhunt = {xivhunt} | instance = {instance}")

        if world not in self._hunts:
            self._hunts[world] = {'horus': {}, 'xivhunt': []}

        _key = f"{name.strip().lower()}_{instance}"

        if name.lower() in self._marks_info.keys():
            hunt = self._marks_info[name.lower()]

            if hunt['Rank'] in ('A', 'S', 'SS', 'SS Minion'):

                if hunt['Rank'] == 'A' and hunt['ZoneName'] in self.EW_ZONES and self._hunts[world]['horus'] is not None:
                    #self._log.info("Endwalker A rank - checking for train...")
                    for key, horusHunt in self._hunts[world]['horus'].items():
                        if horusHunt.rank == 'A' and horusHunt.zone in self.EW_ZONES:
                            if horusHunt.status == horusHunt.STATUS_DIED and int(time.time()) - (int(horusHunt.last_alive) / 1000) <= 120:
                                #self._log.info("Train detected")
                                await self.on_train(world, name, xivhunt, False, instance)
                                #self._log.info("On train call successful")
                                break

                if _key in self._hunts[world]['horus'].keys():
                    if int(time.time()) - (int(self._hunts[world]['horus'][_key].last_alive) / 1000) <= 3600:
                        #self._log.info(f"A hunt was found that just died! Laggy computer? World: {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")
                        return  # Trying to report a hunt that already died in the last 5 minutes. Someone's laggy computer?

                if (xivhunt is not None):
                    if f"{world}_{_key}" in self._timers:
                        if int(time.time()) - (int(self._timers[f"{world}_{_key}"]) / 1000) <= 3600:
                            #self._log.info(f"A hunt was found that just found! Laggy computer? World: {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")
                            return
                    self._timers[f"{world}_{_key}"] = time.time() * 1000;

                self._log.info(f"A hunt has been found on world {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")

                subs = Subscriptions.select().where(
                        (Subscriptions.world == world)
                        & (Subscriptions.category == hunt['Channel'])
                )
                embed = hunt_simple_embed(name, xivhunt=xivhunt)

                #  Checks if another hunt from the same world and expansion has been reported since this one.
                #  If so, report as a new discord message instead of editing.
                #  Fixes the issue of someone scouting hunts in advance and then them not being re-reported when the actual train happens
                if _key in self._hunts[world]['xivhunt']:

                    lastNotificationTime = None

                    if lastNotificationTime is None:
                        lastNotificationTime = time.time();

                    try:
                        lastNotificationTime = int(
                            (
                                # Thanks to the sorting below, [0] will hopefully not be None, if at all possible. Attempt to extract lastNotificationTime
                                lambda f : f[0][0].created_at.replace(tzinfo=datetime.timezone.utc).timestamp() if f[0] is not None else time.time()
                            )
                            (
                                sorted
                                (
                                    # Order the list of notifications, putting any "None" values to the back (there should not be a list though)
                                    (lambda n : [(self._notifications[c][world][_key] if world in self._notifications[c] and _key in self._notifications[c][world] else None) for c in n])
                                    (self._notifications.keys()), # Pass list of notifications keys to n
                                    key=lambda e: e is None # If the previous lamda function returned None, push it to the back of the list
                                )
                            )
                        )
                    except:
                        self._log.exception("Exception thrown")

                    lastNotificationName = name

                    if hunt['Rank'] == 'A':
                        for n_channel in self._notifications:
                            if world in self._notifications:  # Same world?
                                for n_key in self._notifications[n_channel][world]:
                                    n_name = n_key.rsplit("_")[0]

                                    if self._marks_info[n_name]['Rank'] == 'A':
                                        if self.getExpansion(self._marks_info[n_name]) == self.getExpansion(hunt):  # Same expansion?
                                            if self._notifications[n_channel][world][n_key]:
                                                message = self._notifications[n_channel][world][n_key][0]
                                                if int(message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()) > lastNotificationTime:
                                                    lastNotificationTime = int(message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())
                                                    lastNotificationName = n_name

                    if lastNotificationName == name and (int(time.time()) - lastNotificationTime) < 3600:  # If there's been no new reports since, re-report only after 60 minutes
                        self._log.debug(f"{name} on instance {instance} already logged")
                        return
                    else:  # Delete the notification from memory so it sends a new one instead of editing it
                        for n_channel in self._notifications:
                            if world in self._notifications[n_channel]:
                                if _key in self._notifications[n_channel][world]:
                                    async with self.lock:
                                        del self._notifications[n_channel][world][_key]
            else:
                # self._log.debug(f"""Ignoring notifications for {hunt['Rank']} rank hunts""")
                return

        elif name.lower() in self._fates_info.keys():
            if _key in self._hunts[world]['xivhunt']:
                self._log.debug(f"FATE {name} on {world} instance {instance} already logged, updating progress.")
                await self.on_progress(world, name, xivhunt, instance)
                return

            if f"{world}_{_key}" in self._fate_timers:
                if int(time.time()) - (int(self._fate_timers[f"{world}_{_key}"]) / 1000) <= 3600:
                    self._log.info(f"A FATE was found that just found! Laggy computer? World: {world} (Instance {instance}) :: {name}")
                    return
            self._fate_timers[f"{world}_{_key}"] = time.time() * 1000;

            hunt = self._fates_info[name.lower()]
            self._log.info(f"A FATE has been found on world {world} (Instance {instance}) :: {name}")

            subs = Subscriptions.select().where(
                (Subscriptions.world == world)
                & (Subscriptions.category == hunt['Channel'])
            )
            embed = fate_simple_embed(name, xivhunt=xivhunt)

        else:
            self._log.debug(f"""Ignoring notifications for {name}""")
            return

        # Avoid double relaying minions
        if xivhunt['rank'] == "SS Minion":
            minion_key = f"{world}_{_key}"
            if minion_key in self.minions and time.time() - self.minions[minion_key] < 3600: return
            self.minions[minion_key] = time.time()

        for sub in subs:  # type: Subscriptions
            if self.COND_FIND != sub.event:
                continue

            attachcategory = hunt["Name"].lower()

            if hunt['ZoneName'] in self.ARR_ZONES:
                attachcategory = "ARR"
            if hunt['ZoneName'] in self.HW_ZONES:
                attachcategory = "HW"
            if hunt['ZoneName'] in self.SB_ZONES:
                attachcategory = "SB"
            if hunt['ZoneName'] in self.SHB_ZONES:
                attachcategory = "SHB"
            if hunt['ZoneName'] in self.EW_ZONES:
                attachcategory = "EW"
            if hunt['ZoneName'] in self.DT_ZONES:
                attachcategory = "DT"
            if 'Rank' in hunt and hunt['Rank']:
                attachcategory = '_'.join((attachcategory, hunt['Rank'][0:1])).lower()

            _meta = SubscriptionsMeta.select().where((SubscriptionsMeta.channel_id == sub.channel_id)
            & ((SubscriptionsMeta.attachName == hunt["Name"].lower()) | (SubscriptionsMeta.attachName == attachcategory) | (SubscriptionsMeta.attachName is None)))
            # Matches this hunt/fate, hunt category or all's notifier (in that order)
            meta  = {m.name : m.value for m in _meta}
            role_mention = meta['notifier'] if 'notifier' in meta else None

            # content = f"""**{world}** {hunt['Rank']} Rank: **{hunt['Name']}** @ {hunt['ZoneName']} ({xivhunt['coords']}) i{instance}"""
            instancesymbol = "①" if instance == 1 else "②" if instance == 2 else "③" if instance == 3 else "④" if instance == 4 else "⑤" if instance == 5 else "⑥" if instance == 6 else instance

            content = f"""[{world}] {hunt['ZoneName']} ({xivhunt['coords']}) {instancesymbol}"""

            en_zone_name, ja_zone_name = hunt['ZoneName'], self._zones_info[str(hunt['ZoneID'])]['name_ja']
            fr_zone_name, de_zone_name = self._zones_info[str(hunt['ZoneID'])]['name_fr'], self._zones_info[str(hunt['ZoneID'])]['name_de']

            if Worlds.get_world_datacenter(world) in self.JA_DATACENTERS:
                content = f"""[{world}] {ja_zone_name} {hunt['ZoneName']} ({xivhunt['coords']}) {instancesymbol}"""
                ja_description = f"""[{world}] {ja_zone_name} ({xivhunt['coords']}) {instancesymbol}"""
                embed.description = f"""{ja_description}\n{hunt['ZoneName']} ({xivhunt['coords']}) {instancesymbol}"""
            elif Worlds.get_world_datacenter(world) in self.EU_DATACENTERS:
                fr_description = f"""\n{fr_zone_name} ({xivhunt['coords']}) {instancesymbol}""" if fr_zone_name != en_zone_name and fr_zone_name != de_zone_name else ""
                de_description = f"""\n{de_zone_name} ({xivhunt['coords']}) {instancesymbol}""" if de_zone_name != en_zone_name else ""
                embed.description = f"""{content}{fr_description}{de_description}"""
            else:
                embed.description = content

            if name.lower() in self._fates_info.keys(): #  Displaying FATEs a little differently to absorb the information efficiently
                time_left = xivhunt['last_seen']
                remaining_str = RemainingTime(time_left).to_simple()

                fate = self._fates_info[name.lower()]
                duration_str = ""
                if (fate['Duration'] > 0):
                    duration_str = f" / {RemainingTime(fate['Duration']).to_simple()}"

                if Worlds.get_world_datacenter(world) in self.JA_DATACENTERS:
                    embed.description = f"""{xivhunt['status']}% {ja_zone_name} {en_zone_name} ({xivhunt['coords']}) {instancesymbol}"""

                    if time_left > 0:
                        embed.set_footer(text=f"""残り{remaining_str}{duration_str} remaining""")
                elif Worlds.get_world_datacenter(world) in self.EU_DATACENTERS:
                    en_description = f"""{xivhunt['status']}% {en_zone_name} ({xivhunt['coords']}) {instancesymbol}"""
                    fr_description = f"""\n{fr_zone_name} ({xivhunt['coords']}) {instancesymbol}""" if fr_zone_name != en_zone_name and fr_zone_name != de_zone_name else ""
                    de_description = f"""\n{de_zone_name} ({xivhunt['coords']}) {instancesymbol}""" if de_zone_name != en_zone_name else ""
                    embed.description = f"""{en_description}{fr_description}{de_description}"""

                    if time_left > 0:
                        embed.set_footer(text=f"""{remaining_str}{duration_str} remaining / restant""")
                else:
                    embed.description = f"""{xivhunt['status']}% {hunt['ZoneName']} ({xivhunt['coords']}) {instancesymbol}"""

                    if time_left > 0:
                        embed.set_footer(text=f"""{remaining_str}{duration_str} remaining""")

            if role_mention:
                mentionARole = True
                if hunt['ZoneID'] == 1237 or hunt['ZoneID'] == 1291:
                    if instance != 1 and f"{world}_{_key[:-1]}1" in self._fate_timers and (int(time.time()) - (int(self._fate_timers[f"{world}_{_key[:-1]}1"]) / 1000)) <= 2400:
                        mentionARole = False
                        #embed.set_image(url=None)
                    if instance != 2 and f"{world}_{_key[:-1]}2" in self._fate_timers and (int(time.time()) - (int(self._fate_timers[f"{world}_{_key[:-1]}2"]) / 1000)) <= 2400:
                        mentionARole = False
                        #embed.set_image(url=None)
                    if instance != 3 and f"{world}_{_key[:-1]}3" in self._fate_timers and (int(time.time()) - (int(self._fate_timers[f"{world}_{_key[:-1]}3"]) / 1000)) <= 2400:
                        mentionARole = False
                        #embed.set_image(url=None)
                    if instance != 4 and f"{world}_{_key[:-1]}4" in self._fate_timers and (int(time.time()) - (int(self._fate_timers[f"{world}_{_key[:-1]}4"]) / 1000)) <= 2400:
                        mentionARole = False
                        #embed.set_image(url=None)
                    if instance != 5 and f"{world}_{_key[:-1]}5" in self._fate_timers and (int(time.time()) - (int(self._fate_timers[f"{world}_{_key[:-1]}5"]) / 1000)) <= 2400:
                        mentionARole = False
                        #embed.set_image(url=None)
                if mentionARole:
                    content = f"""{role_mention} {content}"""

            if "BlueMageSpells" in hunt and hunt['BlueMageSpells']:
                embed.description = f"""{embed.description}\nBlue Mage Spells: **{hunt['BlueMageSpells']}**"""

                _meta = SubscriptionsMeta.select().where((SubscriptionsMeta.channel_id == sub.channel_id)
                & (SubscriptionsMeta.attachName == "blu_spell"))
                meta  = {m.name : m.value for m in _meta}

                if 'notifier' in meta:
                    content = f"""{content} {meta['notifier']}"""

            message = await self._send_sub_message(content, embed, sub)
            if not message:
                continue

            await self.log_notification(message, sub.channel_id, world, name, instance)

        if subs or not (name.lower() in self._fates_info.keys()):
            self._hunts[world]['xivhunt'].append(_key)

    async def log_notification(self, message: discord.Message, channel: int, world: str, hunt_name: str, instance : int = 1) -> None:
        """
        Log a found notification for editing later
        """
        key = f"{hunt_name.lower()}_{instance}"
        if channel not in self._notifications:
            self._notifications[channel] = {}
        if world not in self._notifications[channel]:
            self._notifications[channel][world] = {}

        log = KillLog.create(hunt_name=hunt_name.lower(), world=world, found=arrow.utcnow().timestamp())
        self._notifications[channel][world][key] = (message, log)
        self._log.debug("Notification message logged: " + repr(message))

    async def get_notification(self, channel: int, world: str, hunt_name: str, instance : int = 1, delete_notification : bool = True) -> typing.Optional[typing.Tuple[discord.Message, KillLog]]:
        """
        Attempt to retrieve a notification message for a previously located hunt or fate
        NOTE: Notifications are automatically purged after retrieved using this method
        """
        key = f"{hunt_name.lower()}_{instance}"
        if channel not in self._notifications or world not in self._notifications[channel]:
            return None

        if key in self._notifications[channel][world]:
            message, log = self._notifications[channel][world][key]
            if delete_notification:
                async with self.lock:
                    del self._notifications[channel][world][key]
            return message, log

        return None

    def get_world(self, id: int):
        try:
            return Worlds.get_world_by_id(id)
        except:
            return None
            raise IndexError(f'No world with the ID {id} could be found')

    def get_zone(self, id: int):
        try:
            return self._zones_info[id]['name']
        except:
            raise IndexError(f'No zone with the ID {id} could be found')

    def get_zone_id(self, name: str):
        try:
            for zone in self._zones_info.values():
                if zone['name'].lower() == name.lower():
                    return zone['id']
        except:
            raise IndexError(f'No zone with the name {name} could be found')

    async def _send_sub_message(self, message, embed: discord.Embed, sub: Subscriptions) -> typing.Optional[discord.Message]:
        """
        Attempt to send a subscription message
        """
        try:
            return await self.bot.get_channel(sub.channel_id).send(message, embed=embed)
        except AttributeError:
            self._log.warning(f"Subscription channel is no longer active; removing channel {sub.channel_id}")
            Subscriptions.delete().where(Subscriptions.channel_id == sub.channel_id).execute()
        except discord.errors.Forbidden:
            self._log.warning(f"No permission to send to channel {sub.channel_id}")

    def _reload(self):
        """
        Save configuration changes
        """
        self._subscriptions = list(Subscriptions.select())
        self._subscriptions_meta = list(SubscriptionsMeta.select())

    def _load_marks(self):
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json'), 'r', encoding='utf-8') as json_file:
            marks = json.load(json_file)

            for _id, mark in marks.items():
                key = mark['Name'].lower()
                self._marks_info[key] = mark

                if mark['ZoneName'] in self.ARR_ZONES and (mark['Rank'][0:1] == 'A' or mark['Rank'][0:1] == 'S'):
                    channel = getattr(self, f"""SUB_ARR_{mark['Rank'][0:1]}""")
                    self._marks_info[key]['Channel'] = channel
                elif mark['ZoneName'] in self.HW_ZONES and (mark['Rank'][0:1] == 'A' or mark['Rank'][0:1] == 'S'):
                    channel = getattr(self, f"""SUB_HW_{mark['Rank'][0:1]}""")
                    self._marks_info[key]['Channel'] = channel
                elif mark['ZoneName'] in self.SB_ZONES and (mark['Rank'][0:1] == 'A' or mark['Rank'][0:1] == 'S'):
                    channel = getattr(self, f"""SUB_SB_{mark['Rank'][0:1]}""")
                    self._marks_info[key]['Channel'] = channel
                elif mark['ZoneName'] in self.SHB_ZONES and (mark['Rank'][0:1] == 'A' or mark['Rank'][0:1] == 'S'):
                    channel = getattr(self, f"""SUB_SHB_{mark['Rank'][0:1]}""")
                    self._marks_info[key]['Channel'] = channel
                elif mark['ZoneName'] in self.EW_ZONES and (mark['Rank'][0:1] == 'A' or mark['Rank'][0:1] == 'S'):
                    channel = getattr(self, f"""SUB_EW_{mark['Rank'][0:1]}""")
                    self._marks_info[key]['Channel'] = channel
                elif mark['ZoneName'] in self.DT_ZONES and (mark['Rank'][0:1] == 'A' or mark['Rank'][0:1] == 'S'):
                    channel = getattr(self, f"""SUB_DT_{mark['Rank'][0:1]}""")
                    self._marks_info[key]['Channel'] = channel
                else:
                    self._log.info(f"""Not binding hunt {mark['Name']} to a subscription channel""")
                    self._log.info(f"{str(mark)} => {mark['ZoneName'] in self.EW_ZONES}")

    def _load_fates(self):
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'fates_info.json'), 'r', encoding='utf-8') as json_file:
            fates = json.load(json_file)
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'achievementfates_info.json'), 'r', encoding='utf-8') as json_file:
            self._achievementfates_info = json.load(json_file)
            fates.update(self._achievementfates_info)

            for _id, fate in fates.items():
                key = fate['Name'].lower()
                self._fates_info[key] = fate
                channel = getattr(self, f"""SUB_FATE""")
                self._fates_info[key]['Channel'] = channel

    def _load_zones(self):
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'zones_info.json'), 'r', encoding='utf-8') as json_file:
            self._zones_info = json.load(json_file)

    def getmarksinfo(self):
        return self._marks_info

    def getfatesinfo(self):
        return self._fates_info

    def getzonesinfo(self):
        return self._zones_info

