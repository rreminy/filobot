import logging, asyncio, typing, discord
import filobot.constants.subscriptions as SUB
import filobot.constants.conditions as COND
from discord.ext.commands import Bot
from filobot.database.models import Subscriptions
from filobot.utilities.worlds import Worlds
from filobot.utilities import *
from filobot.filobot import bot

class SubscriptionManager:

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.subscriptions = list(Subscriptions.select())
        self.lock = asyncio.Lock()

    async def subscribe_all(self, datacenter: str, channel: int, subscription: str, conditions: typing.Optional[str] = 'all'):
        try:
            sub = getattr(SUB, f"""{subscription.upper()}""")
        except AttributeError:
            return "Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"

        if conditions == 'all':
            conditions = list(COND.CONDITIONS)
        else:
            conditions = conditions.replace(' ', '').lower().split(',')
            _invalid_conditions = set(conditions) - set(COND.CONDITIONS)

            if _invalid_conditions:
                return ("Invalid conditions supplied: " + str(_invalid_conditions))

        datacenter = parse_name(datacenter).title()

        if datacenter not in Worlds.get_datacenters():
            return (f"Invalid datacenter provided, valid datacenters are: {', '.join(Worlds.get_datacenters())}")

        async with self.lock:
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

            self.reload()

        message = f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on **all worlds**"""
        return message

    async def subscribe(self, channel: int, world: str, subscription: str, conditions: typing.Optional[str] = 'all'):
        world = parse_name(world).title()

        if world not in Worlds.get_worlds():
            return "No world by that name found - please check your spelling and try again"

        try:
            sub = getattr(SUB, f"""{subscription.upper()}""")
        except AttributeError:
            return "Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"

        if conditions == 'all':
            conditions = list(COND.CONDITIONS)
        else:
            conditions = conditions.replace(' ', '').lower().split(',')
            _invalid_conditions = set(conditions) - set(COND.CONDITIONS)

            if _invalid_conditions:
                    return ("Invalid conditions supplied: " + str(_invalid_conditions))

        async with self.lock:
            if Subscriptions.select().where(
                    (Subscriptions.channel_id == channel)
                    & (Subscriptions.world == world)
                    & (Subscriptions.category == sub)
            ).count():
                return "This channel is already subscribed to this feed. If you want unsubscribe, use the unsub command"

            for condition in conditions:
                Subscriptions.insert({
                    'channel_id': channel,
                    'world'     : world,
                    'category'  : sub,
                    'event'     : condition
                }).execute()

            self.reload()

        message = f"""Subscribed channel to {str(sub).replace('_', ' ').title()} on {world}"""
        return message

    #async def get(self, channel: int) -> typing.List[Subscriptions]:
    async def get(self, channel: int = None, world: str = None, category = None):
        async with self.lock:
            if channel is None and world and category:
                subscription_list = Subscriptions.select().where((Subscriptions.world == world) & (Subscriptions.category == category))
            else:
                subscription_list = list(Subscriptions.select().where(Subscriptions.channel_id == channel))
        return subscription_list

    async def unsubscribe(self, channel: int, world: str, subscription: str):
        world = world.strip().lower().title()

        if world not in Worlds.get_worlds():
            return "No world by that name found - please check your spelling and try again"

        try:
            sub = getattr(SUB, f"""{subscription.upper()}""")
        except AttributeError:
            return "Invalid subscription provided, valid subscriptions are: dt_a, dt_s, ew_a, ew_s, shb_a, shb_s, sb_a, sb_s, hw_a, hw_s, arr_a, arr_s, fate, trains"

        async with self.lock:
            Subscriptions.delete().where(
                    (Subscriptions.channel_id == channel)
                    & (Subscriptions.world == world)
                    & (Subscriptions.category == sub)
            ).execute()

            self.reload()

        message = f"""Unsubscribed channel from {str(sub).replace('_', ' ').title()} on {world}"""
        return message

    async def clear(self, channel: int) -> None:
        async with self.lock:
            Subscriptions.delete().where(Subscriptions.channel_id == channel).execute()
            self.reload()

    def reload(self):
        # Save configuration changes
        self.subscriptions = list(Subscriptions.select())

    async def send_message(self, message, embed: discord.Embed, sub: Subscriptions) -> typing.Optional[discord.Message]:
        try:
            return await bot.get_channel(sub.channel_id).send(message, embed=embed)
        except AttributeError:
            self.log.warning(f"Subscription channel is no longer active; removing channel {sub.channel_id}")
            print("It's about to delete the subscriptions...")

            async with self.lock:
                #Subscriptions.delete().where(Subscriptions.channel_id == sub.channel_id).execute()
                self.reload()
        except discord.errors.Forbidden:
            self.log.warning(f"No permission to send to channel {sub.channel_id}")

