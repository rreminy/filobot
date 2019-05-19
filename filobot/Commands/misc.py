import datetime
import logging
import discord

from discord.ext import commands


class Misc(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

    @commands.command(hidden=True)
    async def ping(self, ctx: commands.context.Context):
        now = datetime.datetime.utcnow().timestamp()
        response_time = now - ctx.message.created_at.timestamp()
        await ctx.send('Boop! Response time: {0} seconds'.format(round(response_time, 1)))

    @commands.command(hidden=True)
    async def off(self, ctx: commands.context.Context):
        word = False  # is the bird the word?

        async for message in ctx.channel.history(limit=10, oldest_first=False):  # type: discord.Message
            if message.author.id == self.bot.user.id:
                continue

            if word:
                await message.add_reaction('🖕')
                break

            if message.id == ctx.message.id:
                word = True
