import time, datetime
import filobot.constants.subscriptions as SUB
import filobot.constants.conditions as COND
import filobot.constants.datacenters as DATACENTERS
import filobot.constants.zones as ZONES
import filobot.utilities.zones as zones
from filobot.utilities import *
from filobot.utilities.worlds import worlds
from filobot.filobot import subscriptions, notifications, log as _log

class TrainManager:

    def __init__(self, marks_info):
        self._marks_info = marks_info
        self._trains = { "DT", "EW", "SHB", "SB" }

    async def on_train(self, world: str, name: str, xivhunt: dict, instance=1):
        hunt = self._marks_info[name.lower()]
        expansion = zones.expansion(hunt['ZoneID'])

        if expansion not in self._trains or (world in self._trains[expansion] and int(time.time()) - self._trains[expansion][world] < 7200):
            return

        self._trains[expansion][world] = int(time.time())
        subs = await subscriptions.get(None, world, getattr(SUB, f"TRAINS_{expansion}".upper()))
        instance_symbol = ZONES.INSTANCE_SYMBOLS.get(instance, str(instance))
        zone_name = f"""{hunt['ZoneName']} {zones.get(str(hunt['ZoneID']))['name_ja']} """ if worlds.get_datacenter(world) in DATACENTERS.JA else f"""{hunt['ZoneName']} """

        for sub in subs:
            if xivhunt is not None:
                content = f"""[{world}] {zone_name}({xivhunt['coords']}) {instance_symbol}"""
            else:
                if COND.DEAD == sub.event:  # Announce train updates using only death reports!
                    content = f"""[{world}] {zone_name} {instance_symbol}"""
                else:
                    continue

            content = f"""{role_mention} {content}""" if role_mention else content
            message = await subscriptions.send_message(content, None, sub)

            if not message:
                continue

            await notifications.log(message, sub.channel_id, world, getattr(SUB, f"TRAINS_{expansion}".upper()), 1)

    async def on_progress(self, world: str, name: str, xivhunt: dict, instance=1):
        hunt = self._marks_info[name.lower()]
        expansion = zones.expansion(hunt['ZoneID'])

        if expansion not in self._trains or (world in self._trains[expansion] and int(time.time()) - self._trains[expansion][world] >= 7200):
            return

        if not xivhunt and world in self._trains[expansion] and int(time.time()) - self._trains[expansion][world] < 5:
            return

        subs = await subscriptions.get(None, world, getattr(SUB, f"TRAINS_{expansion}".upper()))
        instance_symbol = ZONES.INSTANCE_SYMBOLS.get(instance, str(instance))
        zone_name = f"""{hunt['ZoneName']} {zones.get(str(hunt['ZoneID']))['name_ja']} """ if worlds.get_datacenter(world) in DATACENTERS.JA else f"""{hunt['ZoneName']} """

        for sub in subs:
            notification = await notifications.get(sub.channel_id, world, getattr(SUB, f"TRAINS_{expansion}".upper()), 1)

            if xivhunt is not None:
                content = f"""[{world}] {zone_name}({xivhunt['coords']}) {instance_symbol}"""
            else:
                if COND.DEAD == sub.event:  # Announce train updates using only death reports!
                    content = f"""[{world}] {zone_name} {instance_symbol}"""
                else:
                    continue

            content = f"""{role_mention} {content}""" if role_mention else content

            if notification:
                notification, log = notification

                try:
                    if notification.content == content:
                        return

                    await notification.edit(content=content) #  Edit the message
                    await notifications.log(notification, sub.channel_id, world, getattr(SUB, f"TRAINS_{expansion}".upper()), 1)
                    continue
                except discord.NotFound:
                    _log.warning(f"Train announcement was deleted for {world}.")
                except Exception:
                    _log.exception("Exception thrown")

    async def on_end(self, world: str, name: str, xivhunt: dict, instance=1):
        hunt = self._marks_info[name.lower()]
        expansion = zones.expansion(hunt['ZoneID'])

        if expansion not in self._trains or (world in self._trains[expansion] and int(time.time()) - self._trains[expansion][world] >= 7200):
            return

        self._trains[expansion][world] = int(time.time())
        subs = await subscriptions.get(None, world, getattr(SUB, f"TRAINS_{expansion}".upper()))
        role_mention = await notifications.role(sub.channel_id, f"trains_{expansion}")
        instance_symbol = ZONES.INSTANCE_SYMBOLS.get(instance, str(instance))

        for sub in subs:
            notification = await notifications.get(sub.channel_id, world, getattr(SUB, f"TRAINS_{expansion}".upper()), 1)

            content = f"""[{world}]狩ツアコンプリートComplete""" if worlds.get_datacenter(world) in DATACENTERS.JA else f"""[{world}] Complete"""

            if notification:
                notification, log = notification

                try:
                    if notification.content != content:
                        await notification.edit(content=content)
                except discord.NotFound:
                        _log.warning(f"Train announcement was deleted for {world}.")
                except Exception:
                        _log.exception("Exception thrown")

                await notifications.delete(sub.channel_id, world, getattr(SUB, f"TRAINS_{expansion}".upper()), 1)
