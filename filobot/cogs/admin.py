import logging

import discord
from discord import Guild
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

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
