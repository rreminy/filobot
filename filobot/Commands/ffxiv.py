import logging
import re
import discord

from discord.ext import commands
from filobot.utilities.manager import HuntManager
from filobot.models import Player
from filobot.utilities.xivapi import XivApi


class FFXIV(commands.Cog):

    RE_CHAR_STRING = re.compile(r"^(?P<character>[a-zA-Z']+ [a-zA-Z']+)@(?P<world>[a-zA-Z']+)$")

    def __init__(self, bot: discord.ext.commands.Bot, api_key: str):
        self._log = logging.getLogger(__name__)
        self.bot = bot
        self.xiv = XivApi(api_key)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def iam(self, ctx: commands.context.Context, *, name: str):
        """
        Clear recent messages posted by Filo from the channel
        (Will also clear the message used to instantiate this command)
        """
        if Player.select().where(Player.discord_id == ctx.author.id).count():
            await ctx.send("An FFXIV character has already been linked to this Discord account", delete_after=10.0)
            return

        match = self.RE_CHAR_STRING.match(name)
        if not match:
            await ctx.send("Invalid character name provided. Please try again and provide a both the character name and world formatted in `Character Name@World` syntax. For example, `Totomo Omo@Mateus`", delete_after=10.0)
            return

        forename, surname = match.group('character').lower().split(' ')
        world             = match.group('world').lower()

        if world.title() not in HuntManager.WORLDS:
            await ctx.send("Unrecognized world: " + world.title(), delete_after=10.0)
            return

        async with ctx.typing():
            try:
                character = await self.xiv.search_character(world, forename, surname)
            except ValueError as e:
                await ctx.send(str(e))
                return
            await ctx.send(embed=character.embed())
