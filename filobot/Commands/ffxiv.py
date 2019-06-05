import asyncio
import logging
import re
import discord
import typing

import peewee
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
            confirm_message = await ctx.send("An FFXIV character has already been linked to this Discord account. Are you sure you want to replace it? (Y/N)")
            try:
                response = await self.bot.wait_for('message', timeout=15.0, check=self._author_check(ctx.message.author))
                await response.delete()
                await confirm_message.delete()

                if response.content.lower().strip() not in ('y', 'yes'):
                    return
            except asyncio.TimeoutError:
                await confirm_message.delete()
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
                Player.delete().where(Player.discord_id == ctx.author.id)
                lodestone_id, character = await self.xiv.search_character(world, forename, surname)
                try:
                    Player.create(lodestone_id=lodestone_id, discord_id=ctx.author.id, name=character.name, world=character.server)
                except peewee.IntegrityError:
                    await ctx.send("This character has already been linked to another discord user.")
                    return
            except ValueError as e:
                await ctx.send(str(e))
                return
            await ctx.send(embed=character.embed())

    def _author_check(self, author: discord.User) -> typing.Callable:
        """
        Check callback generator for confirmation prompts
        """
        def inner_check(message):
            return message.author == author
        return inner_check
