import logging, time, datetime, asyncio, arrow, discord
import filobot.constants.subscriptions as SUB
import filobot.constants.conditions as COND
import filobot.constants.zones as ZONES
import filobot.constants.datacenters as DATACENTERS
import filobot.utilities.zones as zones
from filobot.filobot import config, subscriptions, notifications, tracker, log
from filobot.utilities import *
from filobot.database.models import SubscriptionsMeta
from filobot.utilities.embeds import hunt_report_embed
from filobot.utilities.bear import BearHunt
from filobot.utilities.worlds import worlds
from filobot.utilities.time_utils import RemainingTime
from filobot.utilities.static_data import marks_info
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

            for prefix, zone_set in ZONES.LIST.items():
                if mark['ZoneName'] in zone_set:
                    self._marks_info[key]['Category'] = getattr(SUB, f"{prefix}_{mark['Rank'][:1]}")
                    break
                else:
                    self._log.info(f"""Not binding hunt {mark['Name']} to a subscription category""")

        self._hunts = tracker._tracked
        self._timers, self._found, self._changed, self._hunt_queue, self.minions = {}, {}, {}, {}, dict()
        self.trains = TrainManager(self._marks_info)

    async def process(self, source, data):
        try:
            alive = data['lastAlive'] == 'True'
            world = worlds.get_world(int(data['wId']))
            hunt = tracker.id_to_hunt(data['id'])
            _plus = 22.5 if hunt['ZoneName'] in ZONES.HW else 21.5

            if not alive or world is None:
                return

            if config.get(source, 'x') == config.get(source, 'y'): # Some JSON structs use an array for X and Y
                data[config.get(source, 'x')] = data[config.get(source, 'x')]['x']
                data[config.get(source, 'y')] = data[config.get(source, 'y')]['y']

            x, y = round((float(data[config.get(source, 'x')]) * 0.02 + _plus)*10)/10, round((float(data[config.get(source, 'y')]) * 0.02 + _plus)*10)/10
            i = data[config.get(source, 'i')] if config.get(source, 'i') in data else 0
            lastreported = data[config.get(source, 'lastReported')]
            last_seen = datetime.datetime.fromisoformat(lastreported).timestamp()

            xivhunt = {
                'rank': hunt['Rank'],
                'status': 'seen', 'last_seen': last_seen,
                'coords': f"{x}, {y}", 'x': x, 'y': y,
                'world': world, 'zone_id': int(data["zoneID"]), 'i': i,
                'players': int(data["players"] if 'players' in data else 4),
                'hp': data["hp"] if "hp" in data else 100
            }

            key = f"{world}_{parse_name(hunt['Name'])}_{i}"

            # A hack to get the correct zone name
            zone = zones.name(data["zoneID"])
            self.get_marks_info()[hunt['Name'].lower()]['ZoneName'] = zone
            self.get_marks_info()[hunt['Name'].lower()]['ZoneID'] = int(data["zoneID"])

            if hunt['Rank'] == "A":
               if xivhunt['players'] < 8 and xivhunt['zone_id'] > 494 and xivhunt['zone_id'] < 962:
                  return
               if xivhunt['players'] < 9 and xivhunt['zone_id'] >= 962:
                  return

            if hunt['Rank'] == "S" and int(float(xivhunt['hp'])) == 100 and 'Players' in hunt and xivhunt['players'] < hunt['Players'] and config.getboolean('Bot', 'PlayerActivityCheck'):
               datacenter = "Undecided"

               try:
                  datacenter = worlds.get_datacenter(world)
               except:
                  self._log.exception('Exception thrown obtaining datacenter')

               if datacenter != "Primal" and datacenter != "Dynamis" and datacenter != "Crystal" and datacenter != "Chaos":
                  key = f"{world}_{parse_name(hunt['Name'])}_{i}"
                  if key not in self._hunt_queue:
                     if hunt['WaitTime'] != 0 and hunt['WaitTime'] != 1560:
                        self._hunt_queue[key] = [data, xivhunt]
                        self._hunt_queue[key][1]['last_seen'] = (int(time.time()) + hunt['WaitTime'])
                     return
                  else:
                     if (int(time.time()) - self._hunt_queue[key][1]['last_seen']) < 0 or (int(time.time()) - self._hunt_queue[key][1]['last_seen']) > 240:
                        return

            if key in self._hunt_queue:
               self._hunt_queue.pop(key)

            if hunt['Rank'] == "SS":
               return

            return await self.on_find(world, hunt['Name'], xivhunt, int(i) or 1)
        except Exception:
            self._log.exception('Exception thrown')
            return

    async def process_chaos(self, source, data, message):
        try:
            alive, zone = True, message.content.split("rank ")[1].split(",")[0].strip()
            hunt, world = None, message.content.split("[")[1].split("]")[0]

            logger.debug(f"Searching for S Rank at: {zone}")

            for mark in self.get_marks_info().values():
                if mark['ZoneName'].lower() == zone.lower() and mark['Rank'] == "S":
                    logger.debug(f"Found: {mark}")
                    hunt = mark
                    break

            if not hunt:
                return

            # A hack to get the correct zone name
            self.get_marks_info()[hunt['Name'].lower()]['ZoneName'] = zone
            self.get_marks_info()[hunt['Name'].lower()]['ZoneID'] = zones.id(zone)
            x, y = message.content.split("(")[1].split(",")[0].strip(), message.content.split("(")[1].split(",")[1].split(")")[0].strip()
            i = message.content.split(")")[1].strip()
            i = int(i if i != "" else 1)

            xivhunt = {
                'rank': hunt['Rank'],
                'status': 'seen', 'last_seen': int(time.time()), 'hp': 100,
                'coords': f"{x}, {y}", 'x': x, 'y': y,
                'world': world, 'zone_id': self.get_marks_info()[hunt['Name'].lower()]['ZoneID'],
            }

            return await self.on_find(world, hunt['Name'], xivhunt, int(i) or 1)
        except:
            self._log.exception('Exception thrown')
            return

    async def on_find(self, world: str, name: str, xivhunt: dict, instance=1):
        self._log.debug(f"on_find: World = {world} | name = {name} | xivhunt = {xivhunt} | instance = {instance}")

        if world not in self._hunts:
            self._hunts[world] = {'tracker': {}, 'xivhunt': []}

        if world not in self._timers:
            self._timers[world] = {}

        _key = f"{parse_name(name)}_{instance}"

        if name.lower() not in self._marks_info or self._marks_info[name.lower()]['Rank'] not in ('A', 'S', 'SS', 'SS Minion'):
            self._log.debug(f"""Ignoring notifications for {name}""")
            return

        hunt = self._marks_info[name.lower()]

        if hunt['Rank'] == 'A' and 'hp' in xivhunt and 'players' in xivhunt:
            if int(float(xivhunt['hp'])) < 99 and xivhunt['players'] > 8:
                await self.trains.on_train(world, name, xivhunt, instance)
            if xivhunt['players'] > 4:
                await self.trains.on_progress(world, name, xivhunt, instance)

        if 'hp' in xivhunt and int(float(xivhunt['hp'])) < 100 and _key in self._timers[world] and int(time.time()) - self._timers[world][_key] > 20:
            await self.on_progress(world, name, xivhunt, instance)
            return

        if ((_key in self._hunts[world]['tracker'] and int(time.time()) - (int(self._hunts[world]['tracker'][_key].last_alive) / 1000) <= 86410) or
        (_key in self._timers[world] and (int(time.time()) - self._timers[world][_key]) <= 86410)):
            return

        self._timers[world][_key] = int(time.time())

        self._log.info(f"A hunt has been found on world {world} (Instance {instance}) :: {name}, Rank {xivhunt['rank']}")

        subs = await subscriptions.get(None, world, hunt['Category'])
        instance_symbol = ZONES.INSTANCE_SYMBOLS.get(instance, str(instance))
        content = f"""[{world}] {hunt['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
        embed = hunt_report_embed(name, xivhunt=xivhunt)
        attach_category = (f"{hunt['Name']}_{hunt['Rank'][0:1]}" if 'Rank' in hunt and hunt['Rank'] else hunt['Name']).lower()

        for prefix, zone_set in ZONES.LIST.items():
            if hunt['ZoneName'] in zone_set:
                attach_category = prefix
                break

        en_zone_name, ja_zone_name = hunt['ZoneName'], zones.get(str(hunt['ZoneID']))['name_ja']
        fr_zone_name, de_zone_name = zones.get(str(hunt['ZoneID']))['name_fr'], zones.get(str(hunt['ZoneID']))['name_de']

        if worlds.get_datacenter(world) in DATACENTERS.JA:
            content = f"""[{world}] {ja_zone_name} {hunt['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
            #ja_description = f"""[{world}] {ja_zone_name} ({xivhunt['coords']}) {instance_symbol}"""
            ja_description = f"""{ja_zone_name} ({xivhunt['coords']}) {instance_symbol}"""
            embed.description = f"""{ja_description}\n{hunt['ZoneName']} ({xivhunt['coords']}) {instance_symbol}"""
        elif worlds.get_datacenter(world) in DATACENTERS.EU:
            fr_description = f"""\n{fr_zone_name} ({xivhunt['coords']}) {instance_symbol}""" if fr_zone_name != en_zone_name and fr_zone_name != de_zone_name else ""
            de_description = f"""\n{de_zone_name} ({xivhunt['coords']}) {instance_symbol}""" if de_zone_name != en_zone_name else ""
            #embed.description = f"""{content}{fr_description}{de_description}"""
            embed.description = f"""{en_zone_name} ({xivhunt['coords']}){fr_description}{de_description}"""
        else:
             embed.description = f"{en_zone_name} ({xivhunt['coords']})" #embed.description = content

        embed.description = f"{xivhunt['hp']}% {embed.description}" if xivhunt and 'hp' in xivhunt else f"100% {embed.description}"

        for sub in subs: # Subscriptions
            if COND.FIND != sub.event:
                continue

            _meta = SubscriptionsMeta.select().where((SubscriptionsMeta.channel_id == sub.channel_id)
            & ((SubscriptionsMeta.attachName == hunt["Name"].lower()) | (SubscriptionsMeta.attachName == attach_category) | (SubscriptionsMeta.attachName is None)))
            # Matches this hunt, hunt category or all's notifier (in that order)
            meta  = {m.name : m.value for m in _meta}
            role_mention = meta['notifier'] if 'notifier' in meta else None
            content = f"""{role_mention} {content}""" if role_mention else content

            if "BlueMageSpells" in hunt and hunt['BlueMageSpells']:
                embed.description = f"""{embed.description}\nBlue Mage Spells: **{hunt['BlueMageSpells']}**"""
                role = await notifications.role(sub.channel_id, "blu_spell")
                content = f"""{content} {role}""" if role else content

            message = await subscriptions.send_message(content, embed, sub)

            if not message:
                continue

            await notifications.log(message, sub.channel_id, world, name, instance)

        self._hunts[world]['xivhunt'].append(_key)

    async def on_progress(self, world: str, name: str, xivhunt: dict, instance=1):
        hunt = self._marks_info[name.lower()]

        if hunt['Rank'] != 'S' or int(float(xivhunt['hp'])) == 0:
            return

        subs = await subscriptions.get(None, world, hunt['Category'])

        for sub in subs:
            notification = await notifications.get(sub.channel_id, world, name, instance)

            if notification:
                notification, log = notification
                content = notification.content
                #content = content.replace(content.rsplit(" ", 1)[1], f"{int(float(xivhunt['hp']))}%")
                embed = notification.embeds[0]
                embed.description = embed.description[embed.description.find("%") + 1:]
                embed.description = f"{int(float(xivhunt['hp']))}%{embed.description}"

                await notification.edit(content=content, embed=embed)

    def get(self, world: str, hunt_name: str, instance=1) -> BearHunt:
        _key = f"{parse_name(hunt_name)}_{instance}"
        return self._hunts[world]['tracker'][f"{parse_name(hunt_name)}_{instance}"]

    async def recheck(self, source: str = None, name: str = None, hunt: BearHunt = None, instance: int = None):
        # Check and update tracker data; calls on_change and on_find events respectively
        if source is None:
            await tracker.update()

            for world in worlds.get_worlds():
                if world not in self._hunts:
                    self._hunts[world] = {'tracker': {}, 'xivhunt': []}

                self._found[world], self._changed[world], job_list = {}, {}, list()
                tracked_list = await tracker.load(world)

                if tracked_list is None:
                    continue

                for key, hunt in tracked_list.items(): # type: str, BearHunt
                    if key in self._hunts[world]['tracker'] and hunt.status != self._hunts[world]['tracker'][key].status:
                        self._log.info(f"""Hunt status for {hunt.name} on {world} (Instance {hunt.instance}) changed - {self._hunts[world]['tracker'][key].status.title()} => {hunt.status.title()}""")
                        self._changed[world][key] = hunt
                        job_list.append(self.on_change(world, self._hunts[world]['tracker'][key], hunt))

                for result in await asyncio.gather(*job_list, return_exceptions=True):
                    if isinstance(result, Exception):
                        self._log.exception("Job failed with exception", exc_info=result)

                self._hunts[world]['tracker'] = tracked_list
        else:
            if hunt.world not in self._hunts:
                self._hunts[world] = {'tracker': {}, 'xivhunt': []}

            self._found[world], self._changed[world], job_list, key = {}, {}, list(), f"{parse_name(name)}_{instance}"

            if key in self._hunts[world]['tracker'] and hunt.status != self._hunts[world]['tracker'][key].status and hunt.open_date > self._hunts[world]['tracker'][key].open_date:
                self._log.info(f"""Hunt status for {name} on {world} (Instance {hunt.instance}) changed - {self._hunts[world]['tracker'][key].status.title()} => {hunt.status.title()}""")
                self._changed[world][key] = hunt
                await self.on_change(world, self._hunts[world]['tracker'][key], hunt)

    async def on_change(self, world: str, old: BearHunt, new: BearHunt):
        hunt = self._marks_info[old.name.lower()]

        if 'Category' not in hunt:
            return

        subs = await subscriptions.get(None, world, hunt['Category'])
        embed = hunt_report_embed(new.name, new)

        for sub in subs:
            if new.status == new.STATUS_OPENED and COND.OPEN == sub.event:
                await subscriptions.send_message(f"A hunt has opened on **{world}** (**Instance {new.instance}**)!", embed, sub)
                continue

            if new.status == new.STATUS_MAXED and COND.OPEN == sub.event:
                await subscriptions.send_message(f"A hunts maximum spawn window has been reached on **{world}** (**Instance {new.instance}**)!", embed, sub)
                continue

            if new.status == new.STATUS_DIED and COND.DEAD == sub.event:
                # If we previously sent a notification that the hunt was found, edit that message instead of sending a new one
                notification = await notifications.get(sub.channel_id, world, new.name, new.instance)
                await notifications.delete(sub.channel_id, world, new.name, new.instance)

                if notification:
                    notification, log = notification
                    ja_seconds, ja_minutes = ("秒", "分") if worlds.get_datacenter(world) in DATACENTERS.JA else ("", "")
                    killed = arrow.get(int(new.last_mark / 1000)).timestamp()
                    seconds = killed - log.found
                    log.killed, log.kill_time = killed, seconds
                    log.save()

                    try:
                        if notification.author.bot:
                            content = f"~~{notification.content}~~ {get_killed_text(seconds, worlds.get_datacenter(world) in DATACENTERS.JA)}"
                            embed.description = f"~~{notification.embeds[0].description}~~" if notification.embeds[0].description else ""
                            embed.set_image(url=None)

                            await notification.edit(content=content, embed=embed)
                    except discord.NotFound:
                        self._log.warning(f"Notification message for hunt {new.name} on world {world} has been deleted")
                    except Exception:
                        self._log.exception("Exception thrown");

            _key = f"{parse_name(new.name)}_{new.instance}"

            if _key in self._hunts[world]['xivhunt']:
                self._hunts[world]['xivhunt'].remove(_key)

        # Check if all A ranks are dead yet so we can end the train
        if hunt['Rank'] == 'A' and self._hunts[world]['tracker'] is not None and new.status == new.STATUS_DIED:
            hunts_living, previous_death, expansion = False, 0, zones.expansion(hunt['ZoneID'])

            for key, tracker_hunt in self._hunts[world]['tracker'].items():
                if tracker_hunt.rank == 'A' and tracker_hunt.zone in getattr(ZONES, f"{expansion}".upper()) and tracker_hunt.name != new.name:
                    if tracker_hunt.status != tracker_hunt.STATUS_DIED:
                        hunts_living = True
                    if tracker_hunt.status == tracker_hunt.STATUS_DIED and int(tracker_hunt.last_alive) / 1000 > previous_death:
                        previous_death = int(tracker_hunt.last_alive) / 1000

            if not hunts_living and int(time.time()) - (int(new.last_alive) / 1000) < 60: # If last death report is retroactive, don't send a random "Complete" message
                await self.trains.on_end(world, new.name, None, new.instance)
                return

            if previous_death and int(int(new.last_alive) / 1000) == int(int(new.last_mark) / 1000): # Don't report a train if it's a retroactive mark
                time_between = (int(new.last_alive) / 1000) - previous_death

                if time_between > 40 and time_between < 240: # More than 40 seconds, less than 4 minutes between deaths?
                    await self.trains.on_train(world, new.name, None, new.instance)
                    await self.trains.on_progress(world, new.name, None, new.instance)

    def get_marks_info(self):
        return self._marks_info
