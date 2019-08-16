import datetime
import logging
import discord
import git

from discord.ext import commands
from filobot.utilities.manager import HuntManager
from filobot.models import ScoutingSessions, Player


class Misc(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot, hunt_manager: HuntManager):
        self._log = logging.getLogger(__name__)
        self.bot = bot
        self._hunt_manager = hunt_manager
        self.start_time = 0

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

    @commands.command()
    async def stats(self, ctx: commands.context.Context):
        """
        Get some miscellaneous bot statistics
        """
        a_count, s_count = await self._hunt_manager.count()
        train_count = ScoutingSessions.select().where(ScoutingSessions.status == ScoutingSessions.STATUS_COMPLETED).count()
        player_count = Player.select().where(Player.status == Player.STATUS_VERIFIED).count()

        # Git build hash
        repo = git.Repo(search_parent_directories=True)
        sha = repo.head.object.hexsha
        short_sha = repo.git.rev_parse(sha, short=1)

        # Uptime
        seconds = round(datetime.datetime.utcnow().timestamp() - self.start_time)
        uptime  = []
        if seconds > 3600:
            uptime.append(f"""{int(seconds / 3600)} hours""")
            seconds -= int(seconds / 3600) * 3600
        if seconds > 60:
            uptime.append(f"""{int(seconds / 60)} minutes""")
            seconds -= int(seconds / 60) * 60

        uptime.append(f"""{int(seconds)} seconds""")

        embed = discord.Embed(title="Support Filo on Ko-fi", description="A Discord FFXIV hunting bot by Totomo Omo from Mateus")
        embed.url = 'https://ko-fi.com/totomo'
        embed.colour = 0x2274A5
        embed.set_thumbnail(url='https://i.imgur.com/khJRCmB.jpg')

        embed.add_field(name='A-Ranks Relayed', value="{:,}".format(a_count))
        embed.add_field(name='S-Ranks Relayed', value="{:,}".format(s_count))
        embed.add_field(name='Hunt Trains Organized', value="{:,}".format(train_count))
        embed.add_field(name='Players Verified', value="{:,}".format(player_count))

        embed.set_footer(text=f"""Build {short_sha} • Up for {', '.join(uptime)}""")

        await ctx.send(embed=embed)

    @commands.Cog.listener('on_ready')
    async def set_start_time(self):
        self.start_time = datetime.datetime.utcnow().timestamp()
