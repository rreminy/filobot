import json
import logging
import os
import sys
import typing

import discord
from discord.ext import commands

from filobot.models import SubscriptionsMeta
from filobot.utilities import hunt_embed, parse_sb_hunt_name, SB_HUNTS
from filobot.utilities.manager import HuntManager
from filobot.utilities.train import Conductor


class Hunts(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot, hunt_manager: HuntManager):
        self._log = logging.getLogger(__name__)
        self.bot = bot

        self.hunt_manager = hunt_manager

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json')) as json_file:
            self.marks_info = json.load(json_file)

        self._trains = {}
        self.hunt_manager.add_recheck_cb(self._update_train)

    @commands.command()
    async def info(self, ctx: commands.context.Context, *, hunt_name: str):
        """
        Return information on the specified hunt target
        """
        try:
            hunt_name = parse_sb_hunt_name(hunt_name)
        except KeyError:
            hunt_name = hunt_name.lower().strip()

        try:
            embed = hunt_embed(hunt_name)
        except KeyError:
            await ctx.send("No hunt by that name found - please check your spelling and try again")
            return

        await ctx.send(embed=embed)

    @commands.command()
    async def status(self, ctx: commands.context.Context, world: str, hunt_name: str, instance: int = 1):
        """
        Retrieve the status of the specified hunt target
        """
        # Make sure the world is properly formatted
        world = world.strip().lower().title()
        try:
            hunt_name = parse_sb_hunt_name(hunt_name)
        except KeyError:
            hunt_name = hunt_name.lower().strip()

        if instance < 1 or instance > 3:
            await ctx.send("Invalid instance provided - please use a number between 1 and 3")
            return

        try:
            horus = self.hunt_manager.get(world, hunt_name, instance)
            embed = hunt_embed(hunt_name, horus)
        except KeyError as e:
            self._log.info(e)
            await ctx.send(
                "No world or hunt by that name found - please check your spelling and try again"
            )
            return

        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def notify(self, ctx: commands.context.Context, role: typing.Optional[discord.Role]):
        """
        Adds a role to mention when hunts are found in this channel
        """
        if not role:
            await self.hunt_manager.remove_notifier(ctx.channel.id)
            await ctx.send("Channel notifier cleared")
            return

        await self.hunt_manager.set_notifier(ctx.channel.id, role)
        await ctx.send("Members of this role will now be notified whenever a new hunt is found. To undo this, run the notify command again without any arguments")

    @commands.command(name='sub-notify')
    @commands.has_permissions(administrator=True)
    async def sub_notify(self, ctx: commands.context.Context, role: typing.Optional[discord.Role]):
        """
        Adds a role to mention when hunts are found in this channel
        """
        if not role:
            await self.hunt_manager.remove_notifier(ctx.channel.id)
            await ctx.send("Channel notifier cleared")
            return

        await self.hunt_manager.set_notifier(ctx.channel.id, role)
        await ctx.send("Members of this role will now be notified whenever a new hunt is found. To undo this, run the notify command again without any arguments")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def sub(self, ctx: commands.context.Context, world: str, category: str, *, conditions: typing.Optional[str] = 'FINDS, DEATHS'):
        """
        Subscribe the channel to hunt events
        Allowed categories: SHB_A, SHB_S, SB_A, SB_S, HW_A, HW_S, ARR_A, ARR_S, FATE, TRAINS
        Allowed conditions: FINDS, DEATHS, OPENINGS
        """
        await self.hunt_manager.subscribe(ctx.channel.id, world, category, conditions)

    @commands.command(name='sub-all')
    @commands.has_permissions(administrator=True)
    async def sub_all(self, ctx: commands.context.Context, datacenter: str, category: str, *, conditions: typing.Optional[str] = 'FINDS, DEATHS'):
        """
        Subscribe the channel to hunt events on ALL of a datacenters worlds
        Allowed datacenters: Aether, Primal, Crystal, Chaos, Light
        Allowed categories: SHB_A, SHB_S, SB_A, SB_S, HW_A, HW_S, ARR_A, ARR_S, FATE, TRAINS
        Allowed conditions: FINDS, DEATHS, OPENINGS
        """
        await self.hunt_manager.subscribe_all(datacenter, ctx.channel.id, category, conditions)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unsub(self, ctx: commands.context.Context, world: str, category: str):
        """
        Subscribe the channel to hunt events
        Allowed categories: SHB_A, SHB_S, SB_A, SB_S, HW_A, HW_S, ARR_A, ARR_S, FATE, TRAINS
        """
        await self.hunt_manager.unsubscribe(ctx.channel.id, world, category)

    @commands.command(name='sub-list')
    @commands.has_permissions(administrator=True)
    async def sub_list(self, ctx: commands.context.Context):
        """
        List all enabled subscriptions for this channel
        """
        subs = await self.hunt_manager.get_subscriptions(ctx.channel.id)

        if not subs:
            await ctx.channel.send(
                    "No subscriptions have been specified for this channel"
            )
            return

        message = ''
        counter = 0
        i = 0
        for sub in subs:
            message = message + f"""\n* {sub.world} — {str(sub.category).upper().replace('_', ' ')} — {sub.event}"""
            i += 1
            counter += 1
            if i > 39:
                await ctx.send("```markdown\n" + message + "```")
                message = ''
                i = 0

        await ctx.send("```markdown\n" + message + "```")

    @commands.command(name='sub-clear')
    @commands.has_permissions(administrator=True)
    async def sub_clear(self, ctx: commands.context.Context):
        """
        Clear all enabled subscriptions for this channel
        """
        try:
            await self.hunt_manager.clear_subscriptions(ctx.channel.id)
        except KeyError as e:
            self._log.info(e)
            await ctx.channel.send(
                    "No subscriptions have been specified for this channel"
            )
            return

        await ctx.send("Subscriptions for this channel have been cleared")

    # @commands.command()
    # async def train(self, ctx: commands.context.Context, world: str, starting_hunt: typing.Optional[str] = 'erle'):
    #     """
    #     Announces the start of a SB hunt train on the specified world
    #     """
    #     world = world.strip().lower().title()
    #     starting_hunt = parse_sb_hunt_name(starting_hunt)
    #
    #     _meta = SubscriptionsMeta.select().where(SubscriptionsMeta.channel_id == ctx.channel.id)
    #     meta = {m.name: m.value for m in _meta}
    #     role_mention = meta['notifier'] if 'notifier' in meta else None
    #
    #     message = f"{ctx.author.mention} has announced the start of a hunt train on **{world.title()}**!"
    #     print(message)
    #     if role_mention:
    #         message = f"{role_mention} {message}"
    #
    #     conductor = Conductor(self.hunt_manager, world, starting_hunt)
    #     self._trains[world] = (
    #         conductor,
    #         await ctx.send(content=message, embed=next(conductor))
    #     )
    #
    #     await ctx.message.delete()
    #
    # @commands.command(name='train-cancel')
    # async def train_cancel(self, ctx: commands.context.Context, world: str):
    #     """
    #     Blows up the train. Boom.
    #     """
    #     world = world.strip().lower().title()
    #     if world not in self._trains:
    #         await ctx.send(f"There are no active trains on **{world.title()} at the moment", delete_after=10.0)
    #         return
    #
    #     conductor, message = self._trains[world]  # type: Conductor, discord.Message
    #     await message.delete()
    #     del self._trains[world]
    #     await ctx.message.delete()

    async def _update_train(self, world, horus):
        if world in self._trains:
            conductor, message = self._trains[world]  # type: Conductor, discord.Message
            killed = False
            for name, horushunt in horus.items():
                # Make sure it's an SB A-Rank
                if name in SB_HUNTS and (horushunt.status == horushunt.STATUS_DIED):
                    if conductor.hunt_is_in_train(name):
                        conductor.log_kill(name)
                        killed = True

            if killed or conductor.finished:
                await message.edit(embed=next(conductor))

            if conductor.finished:
                del self._trains[world]
