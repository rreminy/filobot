import asyncio
import logging
import typing
import uuid

import discord
import peewee
from discord.ext import commands

from filobot.models import GuildSettings, Player
from filobot.utilities.xivapi import XivApi
from filobot.utilities.worlds import Worlds


class FFXIV(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot, api_key: str):
        self._log = logging.getLogger(__name__)
        self.bot = bot
        self.xiv = XivApi(api_key)

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def iam(self, ctx: commands.context.Context, world: str, *, character: str):
        """
        Link your FFXIV character to Filo
        """
        if Player.select().where(Player.discord_id == ctx.author.id).count():
            confirm_message = await ctx.send(f"{ctx.author.mention} An FFXIV character has already been linked to this Discord account. Are you sure you want to replace it? (Y/N)")
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

        if world.title() not in Worlds.get_worlds():
            await ctx.send('Invalid world provided. Please provide the world name first, then your characters first and last names. For example, `f.iam Mateus Totomo Omo`', delete_after=10.0)
            return

        async with ctx.typing():
            try:
                Player.delete().where(Player.discord_id == ctx.author.id).execute()
                lodestone_id, character = await self.xiv.search_character(world, forename, surname)
            except ValueError as e:
                await ctx.send(str(e))
                return
            except TypeError:
                self._log.info("Failed to find character on first query - trying again.")
                try:
                    lodestone_id, character = await self.xiv.search_character(world, forename, surname)
                except TypeError:
                    await ctx.send(f"Unable to find a character by the name of **{character}** on the world **{world.lower().title()}** - Please check your spelling and try again.")
                    return

            try:
                Player.delete().where(
                    (Player.lodestone_id == lodestone_id) & (Player.status == Player.STATUS_PENDING)).execute()
                player = Player.create(lodestone_id=lodestone_id, discord_id=ctx.author.id, name=character.name,
                                       world=character.server, validation_code=uuid.uuid4())
            except peewee.IntegrityError:
                await ctx.send(f"{ctx.author.mention} This character has already been linked to another discord user.")
                return

            await ctx.send(embed=character.embed())
            await ctx.send(f"""{ctx.author.mention} **Note:** Your character has not been validated yet.\n\nTo verify your ownership of this character, please copy and paste the following verification code into your Lodestone Character Profile and then run the `f.verify` command:\n```\n{player.validation_code}\n```\nhttps://na.finalfantasyxiv.com/lodestone/my/setting/profile/""")

    @commands.command()
    @commands.cooldown(2, 15, commands.BucketType.user)
    async def verify(self, ctx: commands.context.Context):
        """
        Verify an account linked with the f.iam command
        """
        try:
            player = Player.get(Player.discord_id == ctx.author.id)
        except peewee.DoesNotExist:
            await ctx.send(f"{ctx.author.mention} You haven't linked your FFXIV account yet! Run the `f.help iam` command for information on how to do this.")
            return

        if player.status == Player.STATUS_BANNED:
            await ctx.send(f"{ctx.author.mention} Your account has been banned and can not be verified again.")
            return
        if player.status == Player.STATUS_VERIFIED:
            await ctx.send(f"{ctx.author.mention} Your account has already been verified!")
            return

        try:
            verified = await self.xiv.verify(lodestone_id=player.lodestone_id, verification_code=player.validation_code)
        except ValueError as e:
            await ctx.send(str(e))
            return

        if verified:
            verified_role = await GuildSettings.fetch('verified', ctx)
            if verified_role:
                print(f"Adding verified role {verified_role} to member {ctx.author.display_name} on guild {ctx.guild.id}")
                await ctx.author.add_roles(verified_role)

            player.status = Player.STATUS_VERIFIED
            player.save()
            verified_message = str(await GuildSettings.fetch('verified_message', ctx)).replace('{mention}', ctx.author.mention)
            await ctx.send(verified_message)
        else:
            await ctx.send(f"{ctx.author.mention} Validation failed. Remember to hit \"confirm\" twice and make sure your character profile contains **only** the following verification code then try again:\n```\n{player.validation_code}\n```")

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def whoami(self, ctx: commands.context.Context):
        """
        Get information on your linked FFXIV character
        """
        try:
            player = Player.get(Player.discord_id == ctx.author.id)
        except peewee.DoesNotExist:
            await ctx.send(f"{ctx.author.mention} You haven't linked your FFXIV account yet! Run the `f.help iam` command for information on how to do this.")
            return

        async with ctx.typing():
            try:
                character = await self.xiv.get_character(player.lodestone_id)
            except ValueError as e:
                await ctx.send(str(e))
                return

        await ctx.send(embed=character.embed(verified=player.status == Player.STATUS_VERIFIED))

    @commands.command()
    @commands.cooldown(2, 15, commands.BucketType.user)
    async def whois(self, ctx: commands.context.Context, member: discord.Member):
        """
        Get the specified discord users FFXIV account
        """
        try:
            player = Player.get(Player.discord_id == member.id)
        except peewee.DoesNotExist:
            await ctx.send(f"{member.display_name} has not linked their FFXIV account to their Discord profile")
            return

        async with ctx.typing():
            try:
                character = await self.xiv.get_character(player.lodestone_id)
            except ValueError as e:
                await ctx.send(str(e))
                return

        await ctx.send(embed=character.embed(verified=player.status == Player.STATUS_VERIFIED))

    def _author_check(self, author: discord.User) -> typing.Callable:
        """
        Check callback generator for confirmation prompts
        """
        def inner_check(message):
            return message.author == author
        return inner_check
