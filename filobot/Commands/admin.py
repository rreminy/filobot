import logging
import discord

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
