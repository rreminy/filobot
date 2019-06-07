import asyncio
import logging
import re
import uuid

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
        Link your FFXIV character to Filo
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
                Player.delete().where(Player.discord_id == ctx.author.id).execute()
                lodestone_id, character = await self.xiv.search_character(world, forename, surname)
                try:
                    Player.delete().where((Player.lodestone_id == lodestone_id) & (Player.status == Player.STATUS_PENDING)).execute()
                    player = Player.create(lodestone_id=lodestone_id, discord_id=ctx.author.id, name=character.name, world=character.server, validation_code=uuid.uuid4())
                except peewee.IntegrityError:
                    await ctx.send("This character has already been linked to another discord user.")
                    return
            except ValueError as e:
                await ctx.send(str(e))
                return

            await ctx.send(embed=character.embed())
            await ctx.send(f"""**Note:** Your character has not been validated yet.\n\nTo verify your ownership of this character, please copy and paste the following verification code into your Lodestone Character Profile and then run the `f.verify` command:\n```\n{player.validation_code}\n```\nhttps://na.finalfantasyxiv.com/lodestone/my/setting/profile/""")

    @commands.command()
    async def verify(self, ctx: commands.context.Context):
        """
        Verify an account linked with the f.iam command
        """
        try:
            player = Player.get(Player.discord_id == ctx.author.id)
        except peewee.DoesNotExist:
            await ctx.send("You haven't linked your FFXIV account yet! Run the `f.help iam` command for information on how to do this.")
            return

        if player.status == Player.STATUS_BANNED:
            await ctx.send("Your account has been banned and can not be verified again.")
            return
        if player.status == Player.STATUS_VERIFIED:
            await ctx.send("Your account has already been verified!")
            return

        verified = await self.xiv.verify(lodestone_id=player.lodestone_id, verification_code=player.validation_code)
        if verified:
            player.status = Player.STATUS_VERIFIED
            player.save()
            await ctx.send("Your account has been verified successfully!")
        else:
            await ctx.send(f"Validation failed. Please make sure your character profile contains **only** the following verification code and then try again:\n```\n{player.validation_code}\n```")

    @commands.command()
    async def whoami(self, ctx: commands.context.Context):
        """
        Get information on your linked FFXIV character
        """
        try:
            player = Player.get(Player.discord_id == ctx.author.id)
        except peewee.DoesNotExist:
            await ctx.send("You haven't linked your FFXIV account yet! Run the `f.help iam` command for information on how to do this.")
            return

        async with ctx.typing():
            character = await self.xiv.get_character(player.lodestone_id)
        await ctx.send(embed=character.embed(verified=player.status == Player.STATUS_VERIFIED))

    def _author_check(self, author: discord.User) -> typing.Callable:
        """
        Check callback generator for confirmation prompts
        """
        def inner_check(message):
            return message.author == author
        return inner_check
