import logging

import discord
import typing

import peewee
from discord import Guild
from discord.ext import commands

from filobot.models import Player


class Admin(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

    @commands.command(hidden=True)
    @commands.is_owner()
    async def ban(self, ctx: commands.context.Context, id: typing.Optional[int] = None):
        """
        Bans a Discord user from accessing Filo
        """
        if ctx.message.mentions:
            user = ctx.message.mentioned[-1]  # type: discord.Member
            id = user.id
        elif not id:
            await ctx.send("Please either mention a discord user to ban or provide their Discord user ID", delete_after=10.0)
            return

        try:
            player = Player.get(Player.discord_id == id)
            player.status = Player.STATUS_BANNED
            player.save()
        except peewee.DoesNotExist:
            player = Player.create(discord_id=id, name="Banned Player", status=Player.STATUS_BANNED)

        await ctx.send(f"Discord member `{id}` banned from accessing Filo")

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def clear(self, ctx: commands.context.Context):
        """
        Clear recent messages posted by Filo from the channel
        (Will also clear the message used to instantiate this command)
        """
        async for message in ctx.channel.history(limit=50):  # type: discord.Message
            if message.author.id == self.bot.user.id:
                await message.delete()

        await ctx.message.delete()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def servers(self, ctx: commands.context.Context):
        output = ''
        counter = 0
        i = 0
        for guild in self.bot.guilds:  # type: Guild
            output = output + f"**{guild.name} ({guild.id})** - {guild.owner.name}#{guild.owner.discriminator}\n"

            i += 1
            counter += 1
            if i > 25:
                await ctx.send(output)
                output = ''
                i = 0

        output = output + f"\n---------------\n**Total servers:** {counter}"
        await ctx.send(output)
