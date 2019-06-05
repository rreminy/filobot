import logging
import re
import discord

from discord.ext import commands
from filobot.utilities.manager import HuntManager
from filobot.models import Player
from filobot.utilities.xivapi import XivApi


class FFXIV(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot, api_key: str):
        self._log = logging.getLogger(__name__)
        self.bot = bot
        self.xiv = XivApi(api_key)

    @commands.command()
    async def iam(self, ctx: commands.context.Context, world: str, *, character: str):
        """
        Clear recent messages posted by Filo from the channel
        (Will also clear the message used to instantiate this command)
        """
        if Player.select().where(Player.discord_id == ctx.author.id).count():
            await ctx.send("An FFXIV character has already been linked to this Discord account", delete_after=10.0)
            return

        try:
            forename, surname = character.lower().split(' ')
            world             = world.lower()
        except ValueError:
            await ctx.send('Invalid character name provided. Please provide the world name first, then your characters first and last names. For example, `f.iam Mateus Totomo Omo`', delete_after=10.0)
            return

        if world.title() not in HuntManager.WORLDS:
            await ctx.send('Invalid world provided. Please provide the world name first, then your characters first and last names. For example, `f.iam Mateus Totomo Omo`', delete_after=10.0)
            return

        async with ctx.typing():
            try:
                character = await self.xiv.search_character(world, forename, surname)
            except ValueError as e:
                await ctx.send(str(e))
                return
            await ctx.send(embed=character.embed())
