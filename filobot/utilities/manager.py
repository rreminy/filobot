import json
import logging
import os
import sys
import typing
import time
import datetime

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


class HuntManager:

    SUB_SHB_A   = 'shadowbringers_a'
    SUB_SHB_S   = 'shadowbringers_s'
    SUB_SB_A    = 'stormblood_a'
    SUB_SB_S    = 'stormblood_s'
    SUB_HW_A    = 'heavensward_a'
    SUB_HW_S    = 'heavensward_s'
    SUB_ARR_A   = 'a_realm_reborn_a'
    SUB_ARR_S   = 'a_realm_reborn_s'
    SUB_FATE    = 'rare_fates'
    SUB_TRAINS   = 'trains'

    HUNT_SUBSCRIPTIONS = ('shb_a', 'shb_s', 'sb_a', 'sb_s', 'hw_a', 'hw_s', 'arr_a', 'arr_s')

    ARR_ZONES = ('Central Shroud', 'East Shroud', 'South Shroud', 'North Shroud', 'Western Thanalan',
                 'Central Thanalan', 'Eastern Thanalan', 'Southern Thanalan', 'Northern Thanalan', 'Middle La Noscea',
                 'Lower La Noscea', 'Eastern La Noscea', 'Western La Noscea', 'Upper La Noscea', 'Outer La Noscea',
                 'Mor Dhona', 'Coerthas Central Highlands')

    HW_ZONES = ('Coerthas Western Highlands', 'The Dravanian Forelands', 'The Dravanian Hinterlands', 'The Churning Mists', 'The Sea of Clouds', 'Azys Lla')

    SB_ZONES = ('The Ruby Sea', 'Yanxia', 'The Azim Steppe', 'The Fringes', 'The Peaks', 'The Lochs')

    SHB_ZONES = ('Il Mheg', "The Rak'tika Greatwood", 'The Tempest', 'Amh Araeng', 'Lakeland', 'Kholusia')

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
        self._fates_info = {}
        self._load_marks()
        self._load_fates()

        self._hunts = {}
        self._changed = {}
        self._found = {}

        # Callbacks
        self._recheck_cbs = []

        # Logged notifications for editing later
        self._notifications = {}

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
        else:
            return "shb"

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

            # Look for updated Horus entries
            for key, hunt in horus.items():  # type: str, HorusHunt
                if key in self._hunts[world]['horus'] and hunt.status != self._hunts[world]['horus'][key].status:
                    self._log.info(f"""Hunt status for {hunt.name} on {world} (Instance {hunt.instance}) changed - {self._hunts[world]['horus'][key].status.title()} => {hunt.status.title()}""")
                    self._changed[world][key] = hunt
                    await self.on_change(world, self._hunts[world]['horus'][key], hunt)

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

    async def on_recheck(self, world: str, horus: HorusHunt):
        for callback in self._recheck_cbs:
            await callback(world, horus)

    def add_recheck_cb(self, callback: typing.Callable):
        if callback in self._recheck_cbs:
            self._log.warning('Callback already defined: ' + repr(callback))
            return

        self._recheck_cbs.append(callback)

    async def check_fates(self):
        for channel in self._notifications:
            for world in self._notifications[channel]:
                for key in self._notifications[channel][world]:
                    name = key.rsplit("_")[0]

                    if self._notifications[channel][world][key] and name in self._fates_info.keys():
                        message, log = self._notifications[channel][world][key]
                        embed = message.embeds[0]
                        secondsLeft = (embed.footer.text.rsplit(":")[0] if embed and isinstance(embed.footer.text, str) else 30) * 60

                        if time.time() >= (int(message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()) + secondsLeft):
                            #  Strikethrough the fate!
                            await self.on_progress(world, self._fates_info[name]['Name'], None, int(key.rsplit("_")[1]))

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
            await self.bot.get_channel(channel).send(
                "No world by that name found - please check your spelling and try again"
            )
            return

        # Validate subscription channel
        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            await self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"
            )
            return

        # Validate conditions
        if conditions == 'all':
            conditions = list(self.CONDITIONS)
        else:
            conditions = conditions.replace(' ', '').lower().split(',')
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

        await self.bot.get_channel(channel).send(f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on {world}""")
        self._reload()

    async def subscribe_all(self, datacenter: str, channel: int, subscription: str, conditions: typing.Optional[str] = 'all'):
        """
        Subscribe a channel to hunt and fate events on all worlds
        """
        # Validate subscription channel
        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            await self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"
            )
            return

        # Validate conditions
        if conditions == 'all':
            conditions = list(self.CONDITIONS)
        else:
            conditions = conditions.replace(' ', '').lower().split(',')
            _invalid_conditions = set(conditions) - set(self.CONDITIONS)
            if _invalid_conditions:
                await self.bot.get_channel(channel).send(
                        "Invalid conditions supplied: " + str(_invalid_conditions)
                )
                return

        # Validate datacenter
        datacenter = datacenter.strip().lower().title()
        if datacenter not in Worlds.get_datacenters():
            await self.bot.get_channel(channel).send(f"Invalid datacenter provided, valid datacenters are: {', '.join(Worlds.get_datacenters())}")
            return

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

        await self.bot.get_channel(channel).send(
            f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on **all worlds**"""
        )
        self._reload()

    async def unsubscribe(self, channel: int, world: str, subscription: str):
        """
        Unsubscribe a channel from hunt and fate events
        """
        world = world.strip().lower().title()
        if world not in Worlds.get_worlds():
            await self.bot.get_channel(channel).send(
                "No world by that name found - please check your spelling and try again"
            )
            return

        try:
            sub = getattr(self, f"""SUB_{subscription.upper()}""")
        except AttributeError:
            await self.bot.get_channel(channel).send(
                "Invalid subscription provided, valid subscriptions are: shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"
            )
            return

        Subscriptions.delete().where(
                (Subscriptions.channel_id == channel)
                & (Subscriptions.world == world)
                & (Subscriptions.category == sub)
        ).execute()

        await self.bot.get_channel(channel).send(f"""Unsubscribed channel from {str(sub).replace('_', ' ').title()} on {world}""")
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

    async def on_progress(self, world: str, name: str, xivhunt: dict, instance=1):
        """
        FATE progress event handler
        """
        fate = self._fates_info[name.lower()]
        subs = Subscriptions.select().where(
                (Subscriptions.world == world)
                & (Subscriptions.category == fate['Channel'])
        )
        embed = fate_simple_embed(name, xivhunt)

        for sub in subs:  # type: Subscriptions
            try:
                # If we previously sent a notification that the fate was found, edit that message instead of sending a new one
                notification = await self.get_notification(sub.channel_id, world, name, instance, False)

                if notification:
                    notification, log = notification

                    # Get the original content
                    content = notification.content

                    time_left = xivhunt['last_seen'] if xivhunt else 0

                    if (not time_left or int(xivhunt['status']) == 100) and self.COND_DEAD == sub.event:
                        killed  = int(time.time())
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

                        # Remove the ping mention
                        beg = content.find(f"[{world}]")
                        content = content[beg:]

                        if time_left:
                            # Add dead timing to message
                            content = f"~~{content}~~ **Killed** *(after {', '.join(kill_time)})*"
                        else:
                            # Add expired message
                            content = f"~~{content}~~ **Expired** *(after {', '.join(kill_time)})*"

                        _key = f"{name.strip().lower()}_{instance}"
                        if _key in self._hunts[world]['xivhunt']:
                            self._hunts[world]['xivhunt'].remove(_key)

                        del self._notifications[sub.channel_id][world][_key]

                    # Set embed description
                    embed = notification.embeds[0]

                    if xivhunt:
                        embed.description = embed.description[embed.description.find("%") + 1:]
                        embed.description = f"{xivhunt['status']}%{embed.description}"

                    if time_left >= 0:
                        embed.set_footer(text=f"""{int(time_left / 60):02d}:{int(time_left % 60):02d} remaining""")

                    # Edit the message
                    await notification.edit(content=content, embed=embed)
                    #  await self.log_notification(notification, sub.channel_id, world, fate['Channel'], instance) #  I think this isn't needed and it'll break another thing
            except discord.NotFound:
                self._log.warning(f"Notification message for FATE {name} on world {world} has been deleted")

    async def on_change(self, world: str, old: HorusHunt, new: HorusHunt):
        """
        Hunt status change event handler
        """
        hunt = self._marks_info[old.name.lower()]
        subs = Subscriptions.select().where(
                (Subscriptions.world == world)
                & (Subscriptions.category == hunt['Channel'])
        )
        embed = hunt_simple_embed(new.name, new)

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

                    try:
                        # Get the original content
                        content = notification.content

                        # Remove the ping mention
                        beg = content.find(f"[{new.world}]")
                        content = content[beg:]

                        # Set embed description
                        embed.description = f"~~{content}~~"

                        # Add dead timing to message
                        content = f"~~{content}~~ **Killed** *(after {', '.join(kill_time)})*"

                        # Edit the message
                        await notification.edit(content=content, embed=embed)
                    except discord.NotFound:
                        self._log.warning(f"Notification message for hunt {new.name} on world {world} has been deleted")

            _key = f"{new.name.strip().lower()}_{new.instance}"
            if _key in self._hunts[world]['xivhunt']:
                self._hunts[world]['xivhunt'].remove(_key)

        # Check if all A ranks are dead yet so we can end the train
        if hunt['Rank'] == 'A' and hunt['ZoneName'] in self.SHB_ZONES and self._hunts[world]['horus'] is not None and new.status == new.STATUS_DIED:
            hunts_living, previous_death = False, 0

            for key, horusHunt in self._hunts[world]['horus'].items():
                if horusHunt.rank == 'A' and horusHunt.zone in self.SHB_ZONES and horusHunt.name != new.name:
                    if horusHunt.status != horusHunt.STATUS_DIED:
                        hunts_living = True
                    if horusHunt.status == horusHunt.STATUS_DIED and int(horusHunt.last_death) / 1000 > previous_death:
                        previous_death = int(horusHunt.last_death) / 1000

            if not hunts_living and int(time.time()) - (int(new.last_death) / 1000) < 60:  # If last death report is retroactive, don't send a random "Complete" message
                # All A ranks are dead, alter the train message
                await self.on_train(world, new.name, None, True, new.instance)
                return

            if previous_death:
                time_between = (int(new.last_death) / 1000) - previous_death

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
                if xivhunt is not None:
                    content = f"""[{world}] {hunt['ZoneName']} ({xivhunt['coords']}) {instancesymbol}"""
                else:
                    if self.COND_DEAD == sub.event:  # Announce train updates using only death reports!
                        content = f"""[{world}] {hunt['ZoneName']} {instancesymbol}"""
                    else:
                        continue

                if role_mention:
                    content = f"""{role_mention} {content}"""
            else:
                content = f"""[{world}] Complete"""

            # Attempt to edit an existing message first
            notification = await self.get_notification(sub.channel_id, world, self.SUB_TRAINS, instance, complete)

            if notification:
                notification, log = notification
                last_train_announcement = int(notification.created_at.timestamp())

                if int(time.time()) - last_train_announcement < 7200: #  Last train announcement less than 2 hours ago? Edit it
                        try:
                            if notification.content != content:
                                await notification.edit(content=content) #  Edit the message
                                await self.log_notification(notification, sub.channel_id, world, self.SUB_TRAINS, instance)
                            continue
                        except discord.NotFound:
                            self._log.warning(f"Train announcement was deleted for {world}.")
                else:
                    if not complete:
                        del self._notifications[sub.channel_id][world][self.SUB_TRAINS]

            if not complete or self.COND_DEAD == sub.event:
                # Sending a new message
                message = await self._send_sub_message(content, None, sub)

                if not message:
                    continue

                await self.log_notification(message, sub.channel_id, world, self.SUB_TRAINS, instance)

    async def on_find(self, world: str, name: str, xivhunt: dict, instance=1):
        """
        Hunt and fate found event handler
        """
        if world not in self._hunts:
            self._hunts[world] = {'horus': {}, 'xivhunt': []}

        _key = f"{name.strip().lower()}_{instance}"

        if name.lower() in self._marks_info.keys():
            hunt = self._marks_info[name.lower()]

            if hunt['Rank'] in ('A', 'S'):

                if _key in self._hunts[world]['horus'].keys() and int(time.time()) - (int(self._hunts[world]['horus'][_key].last_death) / 1000) <= 300:
                    self._log.info(f"A hunt was found that just died! Laggy computer? World: {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")
                    return  # Trying to report a hunt that already died in the last 5 minutes. Someone's laggy computer?

                self._log.info(f"A hunt has been found on world {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")

                subs = Subscriptions.select().where(
                        (Subscriptions.world == world)
                        & (Subscriptions.category == hunt['Channel'])
                )
                embed = hunt_simple_embed(name, xivhunt=xivhunt)

                if hunt['Rank'] == 'A' and hunt['ZoneName'] in self.SHB_ZONES and self._hunts[world]['horus'] is not None:
                    self._log.info("Shadowbringers A rank - checking for train...")
                    for key, horusHunt in self._hunts[world]['horus'].items():
                        if horusHunt.rank == 'A' and horusHunt.zone in self.SHB_ZONES:
                            if horusHunt.status == horusHunt.STATUS_DIED and int(time.time()) - (int(horusHunt.last_death) / 1000) <= 120:
                                self._log.info("Train detected")
                                await self.on_train(world, name, xivhunt, False, instance)
                                self._log.info("On train call successful")
                                break

                #  Checks if another hunt from the same world and expansion has been reported since this one.
                #  If so, report as a new discord message instead of editing.
                #  Fixes the issue of someone scouting hunts in advance and then them not being re-reported when the actual train happens
                if _key in self._hunts[world]['xivhunt']:
                    lastNotificationTime = 0
                    lastNotificationName = name

                    if hunt['Rank'] == 'A':
                        for n_channel in self._notifications:
                            if world in self._notifications:  # Same world?
                                for n_key in self._notifications[n_channel][world]:
                                    n_name = n_key.rsplit("_")[0]

                                    if self._marks_info[n_name]['Rank'] == 'A':
                                        if self.getExpansion(self._marks_info[n_name]) == self.getExpansion(hunt):  # Same expansion?
                                            if self._notifications[n_channel][world][n_key]:
                                                message, log = self._notifications[n_channel][world][n_key]
                                                if int(message.created_at.timestamp()) > lastNotificationTime:
                                                    lastNotificationTime = int(message.created_at.timestamp())
                                                    lastNotificationName = n_name

                    if lastNotificationName == name and (int(time.time()) - lastNotificationTime) < 3600:  # If there's been no new reports since, re-report only after 60 minutes
                        self._log.debug(f"{name} on instance {instance} already logged")
                        return
                    else:  # Delete the notification from memory so it sends a new one instead of editing it
                        for n_channel in self._notifications:
                            if world in self._notifications[n_channel]:
                                if _key in self._notifications[n_channel][world]:
                                    del self._notifications[n_channel][world][_key]
            else:
                self._log.debug(f"""Ignoring notifications for {hunt['Rank']} rank hunts""")
                return

        elif name.lower() in self._fates_info.keys():
            if _key in self._hunts[world]['xivhunt']:
                self._log.debug(f"FATE {name} on instance {instance} already logged, updating progress.")
                await self.on_progress(world, name, xivhunt, instance)
                return

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
            if 'Rank' in hunt and hunt['Rank']:
                attachcategory = '_'.join((attachcategory, hunt['Rank'])).lower()

            _meta = SubscriptionsMeta.select().where((SubscriptionsMeta.channel_id == sub.channel_id)
            & ((SubscriptionsMeta.attachName == hunt["Name"].lower()) | (SubscriptionsMeta.attachName == attachcategory) | (SubscriptionsMeta.attachName is None)))
            # Matches this hunt/fate, hunt category or all's notifier (in that order)
            meta  = {m.name : m.value for m in _meta}
            role_mention = meta['notifier'] if 'notifier' in meta else None

            # content = f"""**{world}** {hunt['Rank']} Rank: **{hunt['Name']}** @ {hunt['ZoneName']} ({xivhunt['coords']}) i{instance}"""
            instancesymbol = "①" if instance == 1 else "②" if instance == 2 else "③" if instance == 3 else instance
            content = f"""[{world}] {hunt['ZoneName']} ({xivhunt['coords']}) {instancesymbol}"""
            embed.description = content

            if name.lower() in self._fates_info.keys(): #  Displaying FATEs a little differently to absorb the information efficiently
                embed.description = f"""{xivhunt['status']}% {hunt['ZoneName']} ({xivhunt['coords']}) {instancesymbol}"""

                time_left = xivhunt['last_seen']

                if time_left > 0:
                    embed.set_footer(text=f"""{(time_left / 60):02d}:{(time_left % 60):02d} remaining""")

            if role_mention:
                content = f"""{role_mention} {content}"""

            message = await self._send_sub_message(content, embed, sub)
            if not message:
                continue

            await self.log_notification(message, sub.channel_id, world, name, instance)

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

        log = KillLog.create(hunt_name=hunt_name.lower(), world=world, found=arrow.utcnow().timestamp)
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
                del self._notifications[channel][world][key]
            return message, log

    def get_world(self, id: int):
        try:
            return Worlds.get_world_by_id(id)
        except:
            raise IndexError(f'No world with the ID {id} could be found')

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
                elif mark['ZoneName'] in self.SHB_ZONES and (mark['Rank'] == 'A' or mark['Rank'] == 'S'):
                    channel = getattr(self, f"""SUB_SHB_{mark['Rank']}""")
                    self._marks_info[key]['Channel'] = channel
                else:
                    self._log.info(f"""Not binding hunt {mark['Name']} to a subscription channel""")

    def _load_fates(self):
        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'fates_info.json')) as json_file:
            fates = json.load(json_file)

            for _id, fate in fates.items():
                key = fate['Name'].lower()
                self._fates_info[key] = fate
                channel = getattr(self, f"""SUB_FATE""")
                self._fates_info[key]['Channel'] = channel

    def getmarksinfo(self):
        return self._marks_info

    def getfatesinfo(self):
        return self._fates_info
