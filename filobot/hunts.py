import logging
import time
import datetime
import asyncio
import arrow
import discord
import filobot.constants.subscriptions as SUB
import filobot.constants.conditions as COND
import filobot.constants.zones as ZONES
import filobot.constants.datacenters as DATACENTERS
import filobot.utilities.zones as zones
from filobot.utilities import *
from filobot.database.models import SubscriptionsMeta
from filobot.utilities.embeds import hunt_report_embed
from filobot.tracker import tracker
from filobot.utilities.bear import BearHunt
from filobot.utilities.worlds import Worlds
from filobot.utilities.time_utils import RemainingTime
from filobot.utilities.static_data import marks_info
from filobot.subscriptions import subscriptions
from filobot.notifications import notifications
from filobot.filobot import log
from filobot.trains import TrainManager

class HuntManager:

    lock = asyncio.Lock()

    def __init__(self):
        self._log = logging.getLogger(__name__)

        self._marks_info = {}

        for _id, mark in marks_info.copy().items():
            key = mark['Name'].lower()
            self._marks_info[key] = mark

            if mark['Rank'][:1] not in {'A', 'S'}:
                continue

            for prefix, zone_set in {'ARR':ZONES.ARR,'HW':ZONES.HW,'SB':ZONES.SB,'SHB':ZONES.SHB,'EW':ZONES.EW,'DT': ZONES.DT}.items():
                if mark['ZoneName'] in zone_set:
                    self._marks_info[key]['Category'] = getattr(SUB, f"{prefix}_{mark['Rank'][:1]}")
                    break
                else:
                    self._log.info(f"""Not binding hunt {mark['Name']} to a subscription category""")
                    self._log.info(f"{str(mark)} => {mark['ZoneName'] in ZONES.EW}")

        self._hunts = {}
        self._changed = {}
        self._found = {}
        self._timers = {}
        self.hunt_queue = {}

        # Minions tracker
        self.minions = dict()

        self.trains = TrainManager(self, self._marks_info)

    async def process(self, source, data):
        try:
            alive   = data['lastAlive'] == 'True'
            world   = Worlds.get_world_by_id(int(data['wId']))
            if world is None:
                return
            hunt    = tracker.id_to_hunt(data['id'])
            _plus   = 22.5 if hunt['ZoneName'] in ZONES.HW else 21.5
            if config.get(source, 'x') == config.get(source, 'y'): # Some JSON structs use an array for X and Y
                data[config.get(source, 'x')] = data[config.get(source, 'x')]['x']
                data[config.get(source, 'y')] = data[config.get(source, 'y')]['y']
            x, y    = round((float(data[config.get(source, 'x')]) * 0.02 + _plus)*10)/10, round((float(data[config.get(source, 'y')]) * 0.02 + _plus)*10)/10
            i = data[config.get(source, 'i')] if config.get(source, 'i') in data else 0
            lastreported = data[config.get(source, 'lastReported')]
            last_seen = datetime.datetime.fromisoformat(lastreported).timestamp()
            xivhunt = {
                'rank': hunt['Rank'],
                'i': i, # data['i'], Seeing as this isn't functional anywhere at the moment
                'status': 'seen' if alive else 'dead',
                'last_seen': last_seen,
                'coords': f"{x}, {y}",
                'world': world,
                'x': x,
                'y': y,
                'zone_id': int(data["zoneID"]),
                'players': int(data["players"] if 'players' in data else 4),
                'hp': data["hp"] if "hp" in data else 100
            }

            # A hack to get the correct zone name
            zone = zones.name(data["zoneID"])
            self.get_marks_info()[hunt['Name'].lower()]['ZoneName'] = zone
            self.get_marks_info()[hunt['Name'].lower()]['ZoneID'] = int(data["zoneID"])

            if not alive:
                return

            if hunt['Rank'] == "A":
               if xivhunt['players'] < 8 and xivhunt['zone_id'] > 494 and xivhunt['zone_id'] < 962:
                  return
               if xivhunt['players'] < 9 and xivhunt['zone_id'] >= 962:
                  return

            key = f"{world}_{parse_name(hunt['Name'])}_{i}"

            if hunt['Rank'] == "S" and int(float(xivhunt['hp'])) == 100 and 'Players' in hunt and xivhunt['players'] < hunt['Players'] and config.getboolean('Bot', 'PlayerActivityCheck'):
               datacenter = "Undecided"

               try:
                  datacenter = worlds.Worlds.get_world_datacenter(world)
               except:
                  self._log.exception('Exception thrown obtaining datacenter')

               if datacenter != "Primal" and datacenter != "Dynamis" and datacenter != "Crystal" and datacenter != "Chaos":
                  key = f"{world}_{parse_name(hunt['Name'])}_{i}"
                  if key not in self.hunt_queue:
                     if hunt['WaitTime'] != 0 and hunt['WaitTime'] != 1560:
                        self.hunt_queue[key] = [data, xivhunt]
                        self.hunt_queue[key][1]['last_seen'] = (int(time.time()) + hunt['WaitTime'])
                     return
                  else:
                     if (int(time.time()) - self.hunt_queue[key][1]['last_seen']) < 0 or (int(time.time()) - self.hunt_queue[key][1]['last_seen']) > 240:
                        return

            if key in self.hunt_queue:
               self.hunt_queue.pop(key)

            if hunt['Rank'] == "SS":
               return

            return await self.on_find(world, hunt['Name'], xivhunt, int(i) or 1)

        except:
            self._log.exception('Exception thrown') # for testing fates stuff
            return

    async def _process_chaos(self, source, data, message):
        try:
            alive   = True
            world   = message.content.split("[")[1].split("]")[0]
            zone    = message.content.split("rank ")[1].split(",")[0].strip()
            hunt    = None
            logger.debug(f"Searching for S Rank at: {zone}")
            for mark in self.get_marks_info().values():
                if mark['ZoneName'].lower() == zone.lower() and mark['Rank'] == "S":
                    logger.debug(f"Found: {mark}")
                    hunt = mark
                    break
            if not hunt:
                return
            x, y    = message.content.split("(")[1].split(",")[0].strip(), message.content.split("(")[1].split(",")[1].split(")")[0].strip()
            i = message.content.split(")")[1].strip()
            i = int(i if i != "" else 1)
            last_seen = int(time.time())
            xivhunt = {
                'rank': hunt['Rank'],
                'i': i, # data['i'], Seeing as this isn't functional anywhere at the moment
                'status': 'seen' if alive else 'dead',
                'last_seen': last_seen,
                'coords': f"{x}, {y}",
                'world': world,
                'x': x,
                'y': y,
                'hp': 100,
                #'zone_id': int(data["zoneID"]), # chaoshunt doesn't have a zone_id but its determined below
            }

            # A hack to get the correct zone name
            self.get_marks_info()[hunt['Name'].lower()]['ZoneName'] = zone
            self.get_marks_info()[hunt['Name'].lower()]['ZoneID'] = zones.id(zone)
            xivhunt["zone_id"] = self.get_marks_info()[hunt['Name'].lower()]['ZoneID']

            if not alive:
                # TODO: Deaths
                return

            return await self.on_find(world, hunt['Name'], xivhunt, int(i) or 1)

        except:
            self._log.exception('Exception thrown') # for testing fates stuff
            return

    def get(self, world: str, hunt_name: str, instance=1) -> BearHunt:
        _key = f"{parse_name(hunt_name)}_{instance}"
        return self._hunts[world]['tracker'][f"{parse_name(hunt_name)}_{instance}"]

    async def recheck(self, source: str = None, name: str = None, hunt: BearHunt = None, instance: int = None):
        """
        Check and update tracker data
        Calls on_change and on_find events respectively
        """
        if source is None:
            await tracker.update()

            for world in Worlds.get_worlds():
                if world not in self._hunts:
                    self._hunts[world] = {'tracker': {}, 'xivhunt': []}

                self._changed[world] = {}
                self._found[world] = {}

                tracked_list = await tracker.load(world)

                if tracked_list is None:
                    continue

                job_list = list()
                for key, hunt in tracked_list.items():  # type: str, BearHunt
                    if key in self._hunts[world]['tracker'] and hunt.status != self._hunts[world]['tracker'][key].status:
                        self._log.info(f"""Hunt status for {hunt.name} on {world} (Instance {hunt.instance}) changed - {self._hunts[world]['tracker'][key].status.title()} => {hunt.status.title()}""")
                        self._changed[world][key] = hunt
                        job_list.append(self.on_change(world, self._hunts[world]['tracker'][key], hunt))
                result = await asyncio.gather(*job_list, return_exceptions=True)
                if isinstance(result, Exception):
                    self._log.exception("Job failed with exception", exc_info=result)

                self._hunts[world]['tracker'] = tracked_list
        else:
            world = hunt.world

            if world not in self._hunts:
                self._hunts[world] = {'tracker': {}, 'xivhunt': []}

            self._changed[world] = {}
            self._found[world] = {}

            key = f"{parse_name(name)}_{instance}"

            job_list = list()
            if key in self._hunts[world]['tracker'] and hunt.status != self._hunts[world]['tracker'][key].status and hunt.open_date > self._hunts[world]['tracker'][key].open_date:
                self._log.info(f"""Hunt status for {name} on {world} (Instance {hunt.instance}) changed - {self._hunts[world]['tracker'][key].status.title()} => {hunt.status.title()}""")
                self._changed[world][key] = hunt
                job_list.append(self.on_change(world, self._hunts[world]['tracker'][key], hunt))
            result = await asyncio.gather(*job_list, return_exceptions=True)
            if isinstance(result, Exception):
                self._log.exception("Job failed with exception", exc_info=result)

    async def on_change(self, world: str, old: BearHunt, new: BearHunt):
        """
        Hunt status change event handler
        """
        hunt = self._marks_info[old.name.lower()]
        if 'Category' not in hunt:
            return
        try:
            subs = subscriptions.get(None, world, hunt['Category'])
            embed = hunt_report_embed(new.name, new)
        except:
            # self._log.warning(f"""{hunt['Name']}""")
            # raise
            return

        for sub in subs:  # type: Subscriptions
            if new.status == new.STATUS_OPENED and COND.OPEN == sub.event:
                await subscriptions.send_message(f"A hunt has opened on **{world}** (**Instance {new.instance}**)!", embed, sub)
                continue

            if new.status == new.STATUS_MAXED and COND.OPEN == sub.event:
                await subscriptions.send_message(f"A hunts maximum spawn window has been reached on **{world}** (**Instance {new.instance}**)!", embed, sub)
                continue

            if new.status == new.STATUS_DIED and COND.DEAD == sub.event:
                # If we previously sent a notification that the hunt was found, edit that message instead of
                # sending a new one
                notification = await notifications.get(sub.channel_id, world, new.name, new.instance)
                await notifications.delete(sub.channel_id, world, new.name, new.instance)
                if notification:
                    notification, log = notification
                    killed  = arrow.get(int(new.last_mark / 1000)).timestamp()
                    seconds = killed - log.found
                    ja_seconds = ""
                    ja_minutes = ""

                    if Worlds.get_world_datacenter(world) in DATACENTERS.JA:
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
                            content = f"~~{content}~~ {get_killed_text(seconds, Worlds.get_world_datacenter(world) in DATACENTERS.JA)}"

                            # Edit the message
                            await notification.edit(content=content, embed=embed)
                    except discord.NotFound:
                        self._log.warning(f"Notification message for hunt {new.name} on world {world} has been deleted")
                    except:
                        self._log.exception("Exception thrown");

            _key = f"{parse_name(new.name)}_{new.instance}"
            if _key in self._hunts[world]['xivhunt']:
                self._hunts[world]['xivhunt'].remove(_key)

        # Check if all A ranks are dead yet so we can end the train
        if hunt['Rank'] == 'A' and hunt['ZoneName'] in ZONES.EW and self._hunts[world]['tracker'] is not None and new.status == new.STATUS_DIED:
            hunts_living, previous_death = False, 0

            for key, trackerHunt in self._hunts[world]['tracker'].items():
                if trackerHunt.rank == 'A' and trackerHunt.zone in ZONES.EW and trackerHunt.name != new.name:
                    if trackerHunt.status != trackerHunt.STATUS_DIED:
                        hunts_living = True
                    if trackerHunt.status == trackerHunt.STATUS_DIED and int(trackerHunt.last_alive) / 1000 > previous_death:
                        previous_death = int(trackerHunt.last_alive) / 1000

            if not hunts_living and int(time.time()) - (int(new.last_alive) / 1000) < 60:  # If last death report is retroactive, don't send a random "Complete" message
                # All A ranks are dead, alter the train message
                await self.trains.on_train(world, new.name, None, True, new.instance)
                return

            if previous_death and int(int(new.last_alive) / 1000) == int(int(new.last_mark) / 1000): # Don't report a train if it's a retroactive mark
                time_between = (int(new.last_alive) / 1000) - previous_death

                if time_between > 40 and time_between < 240:  # More than 40 seconds, less than 4 minutes between deaths?
                    await self.trains.on_train(world, new.name, None, False, new.instance)  # It's a train then

    async def on_find(self, world: str, name: str, xivhunt: dict, instance=1):
        """
        Hunt and fate found event handler
        """
        self._log.debug(f"on_find: World = {world} | name = {name} | xivhunt = {xivhunt} | instance = {instance}")

        if world not in self._hunts:
            self._hunts[world] = {'tracker': {}, 'xivhunt': []}

        _key = f"{parse_name(name)}_{instance}"

        if name.lower() in self._marks_info.keys():
            hunt = self._marks_info[name.lower()]

            if hunt['Rank'] in ('A', 'S', 'SS', 'SS Minion'):

                if hunt['Rank'] == 'A' and hunt['ZoneName'] in ZONES.EW and self._hunts[world]['tracker'] is not None:
                    #self._log.info("Endwalker A rank - checking for train...")
                    for key, trackerHunt in self._hunts[world]['tracker'].items():
                        if trackerHunt.rank == 'A' and trackerHunt.zone in ZONES.EW:
                            if trackerHunt.status == trackerHunt.STATUS_DIED and int(time.time()) - (int(trackerHunt.last_alive) / 1000) <= 120:
                                #self._log.info("Train detected")
                                await self.trains.on_train(world, name, xivhunt, False, instance)
                                #self._log.info("On train call successful")
                                break

                if _key in self._hunts[world]['tracker'].keys():
                    if int(time.time()) - (int(self._hunts[world]['tracker'][_key].last_alive) / 1000) <= 3600:
                        #self._log.info(f"A hunt was found that just died! Laggy computer? World: {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")
                        return  # Trying to report a hunt that already died in the last 5 minutes. Someone's laggy computer?

                if (xivhunt is not None):
                    if f"{world}_{_key}" in self._timers:
                        if int(time.time()) - (int(self._timers[f"{world}_{_key}"]) / 1000) <= 3600:
                            #self._log.info(f"A hunt was found that just found! Laggy computer? World: {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")
                            return
                    self._timers[f"{world}_{_key}"] = time.time() * 1000;

                self._log.info(f"A hunt has been found on world {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")

                subs = subscriptions.get(None, world, hunt['Category'])
                embed = hunt_report_embed(name, xivhunt=xivhunt)

                #  Checks if another hunt from the same world and expansion has been reported since this one.
                #  If so, report as a new discord message instead of editing.
                #  Fixes the issue of someone scouting hunts in advance and then them not being re-reported when the actual train happens
                if _key in self._hunts[world]['xivhunt']:
                    notifications_list = await notifications.list()

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
                                    (lambda n : [(notifications_list[c][world][_key] if world in notifications_list[c] and _key in notifications_list[c][world] else None) for c in n])
                                    (notifications_list.keys()), # Pass list of notifications keys to n
                                    key=lambda e: e is None # If the previous lamda function returned None, push it to the back of the list
                                )
                            )
                        )
                    except:
                        self._log.exception("Exception thrown")

                    lastNotificationName = name

                    if hunt['Rank'] == 'A':
                        for n_channel in notifications_list:
                            if world in notifications_list[n_channel]:  # Same world?
                                for n_key in notifications_list[n_channel][world]:
                                    n_name = n_key.rsplit("_")[0]

                                    if n_name in self._marks_info and self._marks_info[n_name]['Rank'] == 'A':
                                        if zones.expansion(int(self._marks_info[n_name]['ZoneID'])) == zones.expansion(int(hunt['ZoneID'])): # Same expansion?
                                            if notifications_list[n_channel][world][n_key]:
                                                message = notifications_list[n_channel][world][n_key][0]
                                                if int(message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()) > lastNotificationTime:
                                                    lastNotificationTime = int(message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())
                                                    lastNotificationName = n_name

                    if lastNotificationName == name and (int(time.time()) - lastNotificationTime) < 3600:  # If there's been no new reports since, re-report only after 60 minutes
                        self._log.debug(f"{name} on instance {instance} already logged")
                        return
                    else:  # Delete the notification from memory so it sends a new one instead of editing it
                        await notifications.delete(n_channel, world, name, instance)
            else:
                # self._log.debug(f"""Ignoring notifications for {hunt['Rank']} rank hunts""")
                return

        else:
            self._log.debug(f"""Ignoring notifications for {name}""")
            return

        # Avoid double relaying minions
        if xivhunt['rank'] == "SS Minion":
            minion_key = f"{world}_{_key}"
            if minion_key in self.minions and time.time() - self.minions[minion_key] < 3600: return
            self.minions[minion_key] = time.time()

        for sub in subs:  # type: Subscriptions
            if COND.FIND != sub.event:
                continue

            attach_category = hunt["Name"].lower()

            for prefix, zone_set in {'ARR':ZONES.ARR,'HW':ZONES.HW,'SB':ZONES.SB,'SHB':ZONES.SHB,'EW':ZONES.EW,'DT': ZONES.DT}.items():
                if hunt['ZoneName'] in zone_set:
                    attach_category = prefix
                    break

            if 'Rank' in hunt and hunt['Rank']:
                attach_category = '_'.join((attach_category, hunt['Rank'][0:1])).lower()

            _meta = SubscriptionsMeta.select().where((SubscriptionsMeta.channel_id == sub.channel_id)
            & ((SubscriptionsMeta.attachName == hunt["Name"].lower()) | (SubscriptionsMeta.attachName == attach_category) | (SubscriptionsMeta.attachName is None)))
            # Matches this hunt, hunt category or all's notifier (in that order)
            meta  = {m.name : m.value for m in _meta}
            role_mention = meta['notifier'] if 'notifier' in meta else None

            instance_symbol = {1:"①",2:"②",3:"③",4:"④",5:"⑤",6:"⑥"}[instance]
            content = f"""[{world}] {hunt['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""

            en_zone_name, ja_zone_name = hunt['ZoneName'], zones.get(str(hunt['ZoneID']))['name_ja']
            fr_zone_name, de_zone_name = zones.get(str(hunt['ZoneID']))['name_fr'], zones.get(str(hunt['ZoneID']))['name_de']

            if Worlds.get_world_datacenter(world) in DATACENTERS.JA:
                content = f"""[{world}] {ja_zone_name} {hunt['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
                ja_description = f"""[{world}] {ja_zone_name} ({xivhunt['coords']}) {instance_symbol}"""
                embed.description = f"""{ja_description}\n{hunt['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
            elif Worlds.get_world_datacenter(world) in DATACENTERS.EU:
                fr_description = f"""\n{fr_zone_name} ({xivhunt['coords']}) {instance_symbol}""" if fr_zone_name != en_zone_name and fr_zone_name != de_zone_name else ""
                de_description = f"""\n{de_zone_name} ({xivhunt['coords']}) {instance_symbol}""" if de_zone_name != en_zone_name else ""
                embed.description = f"""{content}{fr_description}{de_description}"""
            else:
                embed.description = content

            if role_mention:
                mentionARole = True
                if hunt['ZoneID'] == 1237:
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

                role = notifications.role(sub.channel_id, "blu_spell")

                if role:
                    content = f"""{content} {role}"""

            message = await subscriptions.send_message(content, embed, sub)
            if not message:
                continue

            await notifications.log(message, sub.channel_id, world, name, instance)

        if subs or name.lower() in self._marks_info.keys():
            self._hunts[world]['xivhunt'].append(_key)

    def get_marks_info(self):
        return self._marks_info

hunts = HuntManager(bot)