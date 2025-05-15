import time, datetime
import filobot.constants.subscriptions as SUB
import filobot.constants.conditions as COND
import filobot.constants.datacenters as DATACENTERS
import filobot.utilities.zones as zones
from filobot.utilities import *
from filobot.utilities.worlds import worlds
from filobot.filobot import subscriptions, notifications, log as _log

class TrainManager:

    def __init__(self, marks_info):
        self._marks_info = marks_info

    async def on_train(self, world: str, name: str, xivhunt: dict, complete: bool, instance=1):
        hunt = self._marks_info[name.lower()]

        subs = await subscriptions.get(None, world, getattr(SUB, "TRAINS"))

        instance_symbol = {1:"①",2:"②",3:"③",4:"④",5:"⑤",6:"⑥"}[instance]

        for sub in subs:
            role_mention = await notifications.role(sub.channel_id, "trains")

            # Attempt to edit an existing message first
            notification = await notifications.get(sub.channel_id, world, SUB.TRAINS, 1)

            if not complete:
                zone_name = f"""{hunt['ZoneName']} {zones.get(str(hunt['ZoneID']))['name_ja']} """ if worlds.get_datacenter(world) in DATACENTERS.JA else f"""{hunt['ZoneName']} """

                if xivhunt is not None:
                    content = f"""[{world}] {zone_name}({xivhunt['coords']}) {instance_symbol}"""
                else:
                    if COND.DEAD == sub.event:  # Announce train updates using only death reports!
                        content = f"""[{world}] {zone_name} {instance_symbol}"""
                    else:
                        continue

                if role_mention:
                    content = f"""{role_mention} {content}"""
            else:
                content = f"""[{world}]狩ツアコンプリートComplete""" if worlds.get_datacenter(world) in DATACENTERS.JA else f"""[{world}] Complete"""
                await notifications.delete(sub.channel_id, world, SUB.TRAINS, 1)

            if notification:
                notification, log = notification
                last_train_announcement = int(notification.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())

                if int(time.time()) - last_train_announcement < 7200: #  Last train announcement less than 2 hours ago? Edit it
                        try:
                            if notification.content != content:
                                await notification.edit(content=content) #  Edit the message
                                await notifications.log(notification, sub.channel_id, world, SUB.TRAINS, 1)
                            continue
                        except discord.NotFound:
                            _log.warning(f"Train announcement was deleted for {world}.")
                        except:
                            _log.exception("Exception thrown")
                else:
                    if not complete:
                        await notifications.delete(sub.channel_id, world, SUB.TRAINS, 1)

            if not complete or COND.DEAD == sub.event:
                # Sending a new message
                message = await subscriptions.send_message(content, None, sub)

                if not message:
                    continue

                await notifications.log(message, sub.channel_id, world, SUB.TRAINS, 1)
