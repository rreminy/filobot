import logging, time, datetime, asyncio, discord
import filobot.constants.subscriptions as SUB
import filobot.constants.conditions as COND
import filobot.constants.zones as ZONES
import filobot.constants.datacenters as DATACENTERS
import filobot.utilities.zones as zones
from filobot.filobot import bot, subscriptions, notifications, hunts, tracker, config, log as _log
from filobot.utilities import *
from filobot.database.models import SubscriptionsMeta
from filobot.utilities.embeds import fate_report_embed
from filobot.utilities.worlds import worlds
from filobot.utilities.time_utils import RemainingTime
from filobot.utilities.static_data import fates_info, achievementfates_info

class FateManager:

    lock = asyncio.Lock()

    def __init__(self):
        self._log = _log

        self._fates_info = {}

        for _id, fate in fates_info.items():
            key = fate['Name'].lower()
            self._fates_info[key] = fate
            category = getattr(SUB, f"""FATE""")
            self._fates_info[key]['Category'] = category

        self._fates = tracker._tracked
        self._fate_timers = {}
        self._recent_fates = {}
        self._fate_progress = dict()
        self._fate_start = dict()

    async def process(self, source, data):
        try:
            if (int(data['state']) == 255):
                return

            world = data['world'] if 'world' in data and data['world'] is not None else worlds.get_world(int(data[config.get(source, 'wId')]))
            fate = tracker.id_to_fate(data[config.get(source, 'id')])
            _plus = 22.5 if fate['ZoneName'] in ZONES.HW else 21.5

            if world is None:
                return

            if config.get(source, 'x') == config.get(source, 'y'): # Some JSON structs use an array for X and Y
                data[config.get(source, 'x')] = data[config.get(source, 'x')]['x']
                data[config.get(source, 'y')] = data[config.get(source, 'y')]['y']

            x, y = (data['x'], data['y']) if 'world' in data and data['world'] is not None else (round((float(data[config.get(source, 'x')]) * 0.02 + _plus)*10)/10, round((float(data[config.get(source, 'y')]) * 0.02 + _plus)*10)/10)
            i = data[config.get(source, 'i')] if config.get(source, 'i') in data else 0
            lastreported = data[config.get(source, 'lastReported')]
            last_seen = datetime.datetime.fromisoformat(lastreported).replace(tzinfo=datetime.timezone.utc).timestamp()
            startTimeEpoch = int(data['startTimeEpoch']) if 'startTimeEpoch' in data and data['startTimeEpoch'] and data['startTimeEpoch'].isnumeric() else 0
            duration = int(data['duration']) if 'duration' in data and data['duration'] and data['duration'].isnumeric() else 0
            time_left = (duration - (last_seen - startTimeEpoch)) if duration else -1
            
            xivhunt = {
                'rank': "F",
                'status': data[config.get(source, 'progress')], 'last_seen': time_left,
                'coords': f"{x}, {y}", 'x': x, 'y': y,
                'world': world,
                'zone_id': int(data["zoneID"]), 'i': i,
                'players': int(data["players"] if 'players' in data else 0)
            }

            key = f"{world}_{fate}_{i}"
            fate_info = self.get_fates_info()[fate['Name'].lower()]

            # Update interval
            progressUpdateInterval = 5
            if "ProgressUpdateInterval" in fate_info:
                progressUpdateInterval = fate_info["ProgressUpdateInterval"]

            startTimeEpoch = int(data['startTimeEpoch'])
            progress = int(int(data['progress']) / progressUpdateInterval) * progressUpdateInterval
            xivhunt["status"] = str(progress)

            # Rate limit updates
            if key in self._fate_start and self._fate_start[key] == startTimeEpoch: # Similar to hunt's Actor IDs, startTimeEpoch can be used similarly
                if key in self._fate_progress and self._fate_progress[key] == progress:
                    return

            if str(fate['ID']) in achievementfates_info and (key not in self._fate_start or self._fate_start[key] != startTimeEpoch):
                if progress > 40 or int(time_left / 60) < 8 or (progress <= 11 and 'IgnoreProgress' in fate and fate['IgnoreProgress'] == False):
                    return

            # Update rate limiting check values
            if startTimeEpoch > 0:
                    self._fate_start[key] = startTimeEpoch
            self._fate_progress[key] = progress

            # A hack to get the correct zone name (each fate id is in a unique zone and position, so this should work)
            zone = zones.name(data["zoneID"])
            fate_info['ZoneName'] = zone
            fate_info['ZoneID'] = int(data["zoneID"])

            # Add missing duration to the fate information
            if (not 'Duration' in fate_info) or duration > self.get_fates_info()[fate['Name'].lower()]['Duration']:
                self.get_fates_info()[fate['Name'].lower()]['Duration'] = duration
        except Exception:
            _log.exception('Exception thrown') # for testing fates stuff
            return

        return await self.on_find(world, fate['Name'], xivhunt, int(i) or 1)

    async def on_find(self, world: str, name: str, xivhunt: dict, instance=1):
        self._log.debug(f"fates.on_find: World = {world} | name = {name} | xivhunt = {xivhunt} | instance = {instance}")

        if world not in self._fates:
            self._fates[world] = {'tracker': {}, 'xivhunt': []}

        _key = f"{parse_name(name)}_{instance}"

        if name.lower() not in self._fates_info.keys():
            self._log.debug(f"""Ignoring notifications for {name}""")
            return

        if _key in self._fates[world]['xivhunt']:
            self._log.debug(f"FATE {name} on {world} instance {instance} already logged, updating progress.")
            async with self.lock:
                await self.on_progress(world, name, xivhunt, instance)
            return

        if f"{world}_{_key}" in self._fate_timers:
            if int(time.time()) - (int(self._fate_timers[f"{world}_{_key}"]) / 1000) <= 3600:
                self._log.info(f"A FATE was found that just found! Laggy computer? World: {world} (Instance {instance}) :: {name}")
                return
        self._fate_timers[f"{world}_{_key}"] = time.time() * 1000;

        fate = self._fates_info[name.lower()]
        self._log.info(f"A FATE has been found on world {world} (Instance {instance}) :: {name}")

        subs = await subscriptions.get(None, world, fate['Category'])
        instance_symbol = ZONES.INSTANCE_SYMBOLS.get(instance, str(instance))
        content = f"""[{world}] {fate['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
        embed = fate_report_embed(name, xivhunt=xivhunt)
        remaining_str, time_left = RemainingTime(xivhunt['last_seen']).to_simple(), xivhunt['last_seen']
        duration_str = f" / {RemainingTime(fate['Duration']).to_simple()}" if fate['Duration'] > 0 else ""
        attach_category = fate["Name"].lower()

        for prefix, zone_set in ZONES.LIST.items():
            if fate['ZoneName'] in zone_set:
                attach_category = prefix
                break

        en_zone_name, ja_zone_name = fate['ZoneName'], zones.get(str(fate['ZoneID']))['name_ja']
        fr_zone_name, de_zone_name = zones.get(str(fate['ZoneID']))['name_fr'], zones.get(str(fate['ZoneID']))['name_de']

        if worlds.get_datacenter(world) in DATACENTERS.JA:
            content = f"""[{world}] {ja_zone_name} {fate['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
            ja_description = f"""[{world}] {ja_zone_name} ({xivhunt['coords']}) {instance_symbol}"""
            embed.description = f"""{xivhunt['status']}% {ja_zone_name} {en_zone_name} ({xivhunt['coords']}) {instance_symbol}"""
            footer = f"""残り{remaining_str}{duration_str} remaining"""
        elif worlds.get_datacenter(world) in DATACENTERS.EU:
            en_description = f"""{xivhunt['status']}% {en_zone_name} ({xivhunt['coords']}) {instance_symbol}"""
            fr_description = f"""\n{fr_zone_name} ({xivhunt['coords']}) {instance_symbol}""" if fr_zone_name != en_zone_name and fr_zone_name != de_zone_name else ""
            de_description = f"""\n{de_zone_name} ({xivhunt['coords']}) {instance_symbol}""" if de_zone_name != en_zone_name else ""
            embed.description = f"""{en_description}{fr_description}{de_description}"""
            footer = f"""{remaining_str}{duration_str} remaining / restant"""
        else:
            embed.description = f"""{xivhunt['status']}% {fate['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
            footer = f"""{remaining_str}{duration_str} remaining"""

        if time_left > 0:
            embed.set_footer(text=footer)

        for sub in subs:  # Subscriptions
            if COND.FIND != sub.event:
                continue

            _meta = SubscriptionsMeta.select().where((SubscriptionsMeta.channel_id == sub.channel_id)
            & ((SubscriptionsMeta.attachName == fate["Name"].lower()) | (SubscriptionsMeta.attachName == attach_category) | (SubscriptionsMeta.attachName is None)))
            # Matches this FATE, FATE category or all's notifier (in that order)
            meta  = {m.name : m.value for m in _meta}
            role_mention = meta['notifier'] if 'notifier' in meta else None

            if fate['ZoneID'] == 1237:
                for i in range(1, 6):
                    if instance != i and f"{world}_{_key[:-1]}{i}" in self._fate_timers and (int(time.time()) - (int(self._fate_timers[f"{world}_{_key[:-1]}{i}"]) / 1000)) <= 2400:
                        role_mention = None

            if role_mention:
                content = f"""{role_mention} {content}"""

            if "BlueMageSpells" in fate and fate['BlueMageSpells']:
                embed.description = f"""{embed.description}\nBlue Mage Spells: **{fate['BlueMageSpells']}**"""
                role = await notifications.role(sub.channel_id, "blu_spell")
                if role:
                    content = f"""{content} {role}"""

            message = await subscriptions.send_message(content, embed, sub)

            if not message:
                continue

            await notifications.log(message, sub.channel_id, world, name, instance)

        if subs:
            self._fates[world]['xivhunt'].append(_key)

    async def check(self):
        self._log.debug(f"""Checking FATES""")

        async with self.lock:
            for world in self._recent_fates:
                for recent_fate, expired_time in self._recent_fates[world].items():
                    time_distance = (int(time.time()) - expired_time)
                    # self._log.debug(f"""recent_fate: {repr(recent_fate)}\nexpired_time: {repr(expired_time)}\ntime_distance: {repr(time_distance)}""")
                    if time_distance >= 60 and time_distance < 180:
                        if recent_fate in self._fates[world]['xivhunt']:
                            self._fates[world]['xivhunt'].remove(recent_fate)

            notifications_list, job_list = await notifications.list(), list()
            
            for channel in notifications_list:
                for world in notifications_list[channel]:
                    for key in notifications_list[channel][world]:
                        name = key.rsplit("_")[0]

                        if name in self._fates_info and notifications_list[channel][world][key]:
                            message, log = notifications_list[channel][world][key]
                            message = await message.fetch()

                            try:
                                embed = message.embeds[0]
                            except Exception:
                                continue

                            if not embed:
                                continue

                            seconds_left = RemainingTime.from_simple_time(embed.footer.text if isinstance(embed.footer.text, str) else "30:00").to_seconds()
                            message_time = message.edited_at if message.edited_at is not None else message.created_at

                            self._log.info(f"""edited_at: {repr(message.edited_at)}\ncreated_at: {repr(message.created_at)}""")

                            if int(time.time()) >= int(message_time.timestamp()) + seconds_left: # Strikethrough the fate!
                                # self._log.info(f"""Expiring? Fate: {self._fates_info[name]['Name']} ({world})\n{time.time()} >= {int(message_time.replace(tzinfo=datetime.timezone.utc).timestamp())} + {seconds_left} ({int(message_time.replace(tzinfo=datetime.timezone.utc).timestamp()) + seconds_left})""")
                                job_list.append(self.on_progress(world, self._fates_info[name]['Name'], None, int(key.rsplit("_")[1])))
            for result in await asyncio.gather(*job_list, return_exceptions=True):
                if isinstance(result, Exception):
                    self._log.exception("Job failed with exception", exc_info=result)

    async def on_progress(self, world: str, name: str, xivhunt: dict, instance=1):
        _key = f"{parse_name(name)}_{instance}"
        fate = self._fates_info[name.lower()]
        subs = await subscriptions.get(None, world, fate['Category'])
        embed = fate_report_embed(name, xivhunt)
        time_left = xivhunt['last_seen'] if xivhunt else 0
        is_jp = worlds.get_datacenter(world) in DATACENTERS.JA
        ja_seconds, ja_minutes = ("秒", "分") if is_jp else ("", "")

        for sub in subs:  # type: Subscriptions
            try:
                notification = await notifications.get(sub.channel_id, world, name, instance) # Editing existing message, hopefully

                if notification:
                    notification, log = notification
                    notification = await notification.fetch()
                    content = notification.content
                    embed = notification.embeds[0]

                    if (not time_left or int(xivhunt['status']) == 100) and COND.DEAD == sub.event:
                        killed = notification.edited_at.replace(tzinfo=datetime.timezone.utc).timestamp() if not time_left and notification.edited_at is not None else int(time.time())
                        seconds = killed - log.found
                        log.killed, log.kill_time = killed, seconds
                        log.save()

                        if time_left:
                            self._log.debug(f"FATE {name} on world {world} instance {instance} killed [1]\n{repr(xivhunt)}")
                            content = f"~~{content}~~ {get_killed_text(seconds, is_jp)}"
                        elif (xivhunt is not None and int(xivhunt['status']) > 0):
                            if notification.edited_at is not None and (time.time() - notification.edited_at.timestamp()) > 120:
                                self._log.debug(f"FATE {name} on world {world} instance {instance} killed [2]\n{repr(xivhunt)}")
                                content = f"~~{content}~~ {get_killed_text(seconds, is_jp)}"
                            else:
                                self._log.debug(f"FATE {name} on world {world} instance {instance} expired [1]\n{repr(xivhunt)}")
                                content = f"~~{content}~~ {get_expired_text(seconds, is_jp)}"
                        else:
                            self._log.debug(f"FATE {name} on world {world} instance {instance} expired [2]\n{repr(xivhunt)}")
                            content = f"~~{content}~~ {get_expired_text(seconds, is_jp)}"

                        if await notifications.get(sub.channel_id, world, name, instance) is None:
                            return

                        await notifications.delete(sub.channel_id, world, name, instance)

                    if xivhunt:
                        self._log.debug(f"FATE {name} on world {world} instance {instance} data\n{repr(xivhunt)}")
                        embed.description = embed.description[embed.description.find("%") + 1:]
                        embed.description = f"{xivhunt['status']}%{embed.description}"

                    if content[0] == "~":
                        embed.set_image(url=None)

                    if time_left >= 0:
                        remaining_str = RemainingTime(time_left).to_simple()
                        duration_str = f" / {RemainingTime(fate['Duration']).to_simple()}" if fate['Duration'] > 0 else ""

                        if is_jp:
                            embed.set_footer(text=f"""残り{remaining_str}{duration_str} remaining""")
                        elif worlds.get_datacenter(world) in DATACENTERS.EU:
                            embed.set_footer(text=f"""{remaining_str}{duration_str} remaining / restant""")
                        else:
                            embed.set_footer(text=f"""{remaining_str}{duration_str} remaining""")

                    await notification.edit(content=content, embed=embed)
            except discord.NotFound:
                self._log.warning(f"Notification message for FATE {name} on world {world} has been deleted")

        if (not time_left or int(xivhunt['status']) == 100): 
            if _key in self._fates[world]['xivhunt']:
                if world not in self._recent_fates:
                    self._recent_fates[world] = {}
                if _key not in self._recent_fates[world]:
                    self._recent_fates[world][_key] = int(time.time())

    def get_fates_info(self):
        return self._fates_info
