import logging
import asyncio
import typing
import discord
import arrow
import copy
from filobot.database.models import SubscriptionsMeta, KillLog

class NotificationManager:

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self.notifications = {}
        self.subscriptions_meta = list(SubscriptionsMeta.select())
        self.lock = asyncio.Lock()

    async def set(self, channel: int, role: discord.Role, attachname: str) -> None:
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

        self.reload()

    async def remove(self, channel: int) -> None:
        SubscriptionsMeta.delete().where(
                (SubscriptionsMeta.channel_id == channel)
                & (SubscriptionsMeta.name == 'notifier')
        ).execute()

        self.reload()

    async def log(self, message: discord.Message, channel: int, world: str, hunt_name: str, instance : int = 1) -> None:
        key = f"{hunt_name.lower()}_{instance}"

        async with self.lock:
            if channel not in self.notifications:
                self.notifications[channel] = {}
            if world not in self.notifications[channel]:
                self.notifications[channel][world] = {}

            log = KillLog.create(hunt_name=hunt_name.lower(), world=world, found=arrow.utcnow().timestamp())
            self.notifications[channel][world][key] = (message, log)

        self._log.debug("Notification message logged: " + repr(message))

    async def get(self, channel: int, world: str, hunt_name: str, instance : int = 1) -> typing.Optional[typing.Tuple[discord.Message, KillLog]]:
        key = f"{hunt_name.lower()}_{instance}"

        async with self.lock:
            if channel not in self.notifications or world not in self.notifications[channel]:
                return None

            if key in self.notifications[channel][world]:
                message, log = self.notifications[channel][world][key]
                return message, log

        return None

    async def list(self):
        async with self.lock:
            copy = {}

            for channel, worlds in self.notifications.items():
                copy[channel] = {}

                for world, keys in worlds.items():
                    copy[channel][world] = dict(keys)

            return copy

    async def delete(self, channel: int, world: str, hunt_name: str, instance : int = 1):
        key = f"{hunt_name.lower()}_{instance}"

        async with self.lock:
            if channel not in self.notifications or world not in self.notifications[channel]:
                return

            if key in self.notifications[channel][world]:
                del self.notifications[channel][world][key]

        return

    # Total number of notifications sent
    async def count(self) -> typing.Tuple[int, int]:
        a_count = list(SubscriptionsMeta.select(fn.SUM(SubscriptionsMeta.value).alias('total')).where(SubscriptionsMeta.name == 'a_count'))[0].total or 0
        s_count = list(SubscriptionsMeta.select(fn.SUM(SubscriptionsMeta.value).alias('total')).where(SubscriptionsMeta.name == 's_count'))[0].total or 0

        return (a_count, s_count)

    def reload(self):
        self.subscriptions_meta = list(SubscriptionsMeta.select())

notifications = NotificationManager()
