import asyncio
import datetime
import os
import logging
import re
import sys
import arrow
import pystache
import discord
import typing

from discord.ext import commands
from peewee import fn, SQL
from filobot.utilities import parse_sb_hunt_name
from filobot.utilities.manager import HuntManager
from filobot.models import ScoutingSessions, ScoutingHunts


class Scouting(commands.Cog):

    _message: typing.Optional[discord.Message]
    _previous_message: typing.Optional[discord.Message]
    _channel: typing.Optional[discord.TextChannel]
    _previous_channel: typing.Optional[discord.TextChannel]
    _session: typing.Optional[ScoutingSessions]
    _previous_session: typing.Optional[ScoutingSessions]

    HUNTS = {
        'erle': {'loc': None, 'scout': None},
        'orcus': {'loc': None, 'scout': None},

        'aqrabuamelu': {'loc': None, 'scout': None},
        'vochstein': {'loc': None, 'scout': None},

        'luminare': {'loc': None, 'scout': None},
        'mahisha': {'loc': None, 'scout': None},


        'funa yurei': {'loc': None, 'scout': None},
        'oni yumemi': {'loc': None, 'scout': None},

        'angada': {'loc': None, 'scout': None},
        'gajasura': {'loc': None, 'scout': None},

        'girimekhala': {'loc': None, 'scout': None},
        'sum': {'loc': None, 'scout': None},
    }

    ALIASES = [('aqra', 'aqrabuamelu'), ('voch', 'vochstein'), ('lumi', 'luminare'), ('mahi', 'mahisha'),
               ('funa', 'funa yurei'), ('oni', 'oni yumemi'), ('anga', 'angada'), ('gaja', 'gajasura'),
               ('giri', 'girimekhala')]

    REFRESH_AFTER = 6  # messages

    # _RE = re.compile(r"^(?P<hunt>[\w\s]+)\s+[^\w\s]+\s*\W?(?P<zone>[\w\s]+)\s(?P<coords>\([^\\)]+\))(\s+\W*(?P<scout>[\w\s]+))?.*$")
    _RE = re.compile(r"^(?P<hunt>[a-zA-Z\s]+)\s*\D+(?P<coords>[\d\\.]+\s*,\s*[\d\\.]+)(\s+\W*(?P<scout>[\w\s']+))?")

    def __init__(self, bot: discord.ext.commands.Bot, hunt_manager: HuntManager):
        self._log = logging.getLogger(__name__)
        self.bot = bot
        self.hunt_manager = hunt_manager

        self.started = False

        self._hunts = self.HUNTS.copy()
        self._previous_hunts = None

        self._message = None
        self._previous_message = None
        self._channel = None
        self._previous_channel = None
        self._session = None
        self._previous_session = None

        # Off-topic banter counter; after self.REFRESH_AFTER messages, the scouting tracker is reposted
        self._banter_count = 0

        self._action_logs = []

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'scouting.md'), encoding='utf8') as tf:
            self.template = tf.read()

    @commands.command()
    async def start(self, ctx: commands.context.Context):
        """
        Start a new scouting session
        """
        if self.started:
            await ctx.send("A scouting session has already been started - run **f.cancel** first to start a new session")
            return

        self._session = ScoutingSessions.create(
            channel_id=ctx.channel.id,
            started_by=ctx.author.id,
            status=ScoutingSessions.STATUS_STARTED,
            scouts=''
        )

        self._hunts = self.HUNTS.copy()
        self.started = True
        self._channel = ctx.channel

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} has initialized a new scouting session"""
        self._log_action(_action)

        await ctx.message.delete()
        self._message = await ctx.send(f"""@here {ctx.author.mention} has started a new scouting session! Please check the Party Finder to join in.\n{self.render()}""")

    @commands.command()
    async def add(self, ctx: commands.context.Context, *, entry: str):
        """
        Add a hunt entry to the scouting list
        """
        entry = re.sub(r"Z: \d+\.\d+", '', entry).strip()  # Strip height index from flags
        match = self._RE.match(entry)

        if not match:
            await ctx.message.delete()
            await ctx.send("Unable to parse hunt location — Make sure your hunts are formatted properly. For example..\n```Erle - The Fringes ( 14.5  , 12.4 ) (Scouting Player)```", delete_after=10.0)
            return

        try:
            hunt    = parse_sb_hunt_name(match.group('hunt'))
            coords  = f"""( {match.group('coords')} )"""
            scout   = match.group('scout') or ctx.author.display_name
            scout   = scout[:30]
        except KeyError:
            await ctx.message.delete()
            await ctx.send("Unknown hunt target: " + match.group('hunt')[:30], delete_after=10.0)
            return

        # Are we trying to overwrite an already scouted hunt?
        if self._hunts[hunt]['loc']:
            confirm_message = await ctx.send(f"""The hunt {hunt.title()} has already been scouted. Are you sure you want to overwrite it? (Y/N)""")

            try:
                response = await self.bot.wait_for('message', timeout=10.0, check=self._author_check(ctx.message.author))
                confirmed = response.content.lower().strip() in ('y', 'yes')
                await response.delete()
            except asyncio.TimeoutError:
                confirmed = False

            if confirmed:
                # Log the action
                _action = f"""{ctx.author.name}#{ctx.author.discriminator} overwrote the hunt target {hunt.title()} {coords} — {scout}"""
                self._log_action(_action)

                # Update hunt entry
                self._hunts[hunt] = {'loc': coords, 'scout': scout}
                await self._update(ctx)
            else:
                self._log.info("Not overwriting hunt target " + hunt.title())

            await ctx.message.delete()
            await confirm_message.delete()
            return

        ScoutingHunts.create(
            scouting_session=self._session,
            hunt=hunt,
            scouted_by=scout,
            discord_user=ctx.author.id
        )

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} scouted the hunt target {hunt.title()} {coords} — {scout}"""
        self._log_action(_action)

        # Update hunt entry
        self._hunts[hunt] = {'loc': coords, 'scout': scout}
        await ctx.message.delete()
        await self._update(ctx)

    @commands.command()
    async def addsniped(self, ctx: commands.context.Context, *, hunt_name: str):
        """
        Mark a hunt as sniped
        """
        try:
            hunt  = parse_sb_hunt_name(hunt_name)
            scout = ctx.author.name
        except KeyError:
            self._log.info("Invalid hunt name: " + hunt_name)
            await ctx.message.delete()
            await ctx.send("Unknown hunt target: " + hunt_name[:30], delete_after=10.0)
            return

        # Are we trying to overwrite an already scouted hunt?
        if self._hunts[hunt]['loc']:
            confirm_message = await ctx.send(f"""The hunt {hunt.title()} has already been scouted. Are you sure you want to mark it as sniped? (Y/N)""")

            try:
                response = await self.bot.wait_for('message', timeout=10.0, check=self._author_check(ctx.message.author))
                confirmed = response.content.lower().strip() in ('y', 'yes')
                await response.delete()
            except asyncio.TimeoutError:
                confirmed = False

            if confirmed:
                # Log the action
                _action = f"""{ctx.author.name}#{ctx.author.discriminator} overwrote the hunt target {hunt.title()} — Sniped"""
                self._log_action(_action)

                # Update hunt entry
                self._hunts[hunt] = {'loc': '(Sniped)', 'scout': scout}
                await self._update(ctx)
            else:
                self._log.info("Not overwriting hunt target " + hunt.title())

            await ctx.message.delete()
            await confirm_message.delete()
            return

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} marked the hunt target {hunt.title()} sniped"""
        self._log_action(_action)

        # Update hunt entry
        self._hunts[hunt] = {'loc': '(Sniped)', 'scout': scout}
        await ctx.message.delete()
        await self._update(ctx)

    @commands.command()
    async def end(self, ctx: commands.context.Context):
        """
        Close an active scouting session and log the completion time
        """
        if not self.started:
            await ctx.send("There is no active scouting session to conclude.", delete_after=5.0)
            return

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} has concluded a scouting session"""
        self._log_action(_action)

        scouts = set()
        for hunt in self._hunts.values():
            if hunt['scout']:
                scouts.add(hunt['scout'])

        self._session.status = ScoutingSessions.STATUS_COMPLETED
        self._session.scouts = ','.join(scouts)
        self._session.save()

        scouts = "\n* ".join(scouts)
        scouts = f"""\n```markdown\nScouts: \n* {scouts}```""" if scouts else ''

        now = arrow.now().format("MMM Do, H:mma ZZZ")
        await self._update(ctx, f"""Hunt session concluded **{now}**{scouts}""")
        self._reset()

        await ctx.message.delete()

    @commands.command()
    async def cancel(self, ctx: commands.context.Context):
        """
        Cancel a previously initialized scouting session
        """
        if not self.started:
            await ctx.send("There is no active scouting session to cancel.", delete_after=5.0)
            return

        try:
            await self._message.delete()
        except discord.NotFound:
            self._log.warning("Scouting session cancelled, but the scouting message was already deleted")

        self._session.status = ScoutingSessions.STATUS_CANCELLED
        self._session.save()
        self._reset()

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} has cancelled an active hunting session"""
        self._log_action(_action)

        await ctx.message.delete()
        await ctx.send("Scouting cancelled!", delete_after=5.0)

    @commands.command()
    async def restore(self, ctx: commands.context.Context) -> None:
        """
        Restore a previously concluded hunt
        """
        if self.started:
            await self._message.delete()
            await ctx.send("You cannot restore a previous hunt session when another is already in progress!", delete_after=10.0)
            return

        self._hunts = self._previous_hunts
        self._message = self._previous_message
        self._channel = self._previous_channel
        self._session = self._previous_session
        self.started = True

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} restored a previous scouting session"""
        self._log_action(_action)

        await ctx.message.delete()
        await ctx.send("Scouting restored!", delete_after=5.0)
        await self._update(ctx)

    @commands.command()
    async def refresh(self, ctx: commands.context.Context):
        """
        Delete and repost the scouting tracker as the most recent message
        Forcefully deletes and reposts the scouting tracker in the event it becomes buried in off-topic banter
        Note: This is normally done automatically after 6 messages
        """
        await ctx.message.delete()

        if not self.started:
            await ctx.send("There's no active scouting session to refresh!", delete_after=10.0)
            return

        await self._message.delete()
        self._message = await ctx.send(self.render())
        self._banter_count = 0

    @commands.command()
    async def logs(self, ctx: commands.context.Context):
        """
        Display the scouting action logs
        """
        await ctx.message.delete()

        if not self._action_logs:
            await ctx.send("Not actions have been performed yet!")
            return

        message = "```markdown\nAction logs:"
        for action in self._action_logs:
            message = message + f"""\n* {action}"""
        message = message + "\n```"

        await ctx.send(message)

    @commands.command()
    async def scoreboard(self, ctx: commands.context.Context, days: int = 30, limit: int = 10):
        """
        Hunt leaders - run f.help scoreboard for more information
        Display a leaderboard of the top scouters over the last XX days

        NOTE:
            * Overwriting hunts will not increase your total
            * You will get credit even if you post relayed hunts, so give the original relayers credit too!
        """
        if days < 1 or days > 365:
            await ctx.send("Days must be between 1 and 365", delete_after=10.0)
            await ctx.message.delete()
            return

        if limit < 3 or limit > 25:
            await ctx.send("Limit must be between 3 and 25", delete_after=10.0)
            await ctx.message.delete()
            return

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        query = ScoutingHunts.select(ScoutingHunts.discord_user, fn.COUNT(ScoutingHunts.discord_user).alias('score')).join(ScoutingSessions)\
            .where((ScoutingSessions.status != ScoutingSessions.STATUS_CANCELLED) & (ScoutingSessions.date >= cutoff))\
            .group_by(ScoutingHunts.discord_user)\
            .order_by(SQL('score').desc())

        message = f"""```markdown\nScoreboard ({days} days)\n"""
        message = message + "=" * len(f"""Scoreboard ({days} days)""") + "\n"

        total = sum(s.score for s in query)
        scores = []
        for score in query:
            percentage = round((score.score / total) * 100)
            scores.append((score.discord_user, score.score, percentage))

        position = 1
        if scores:
            for discord_user, score, percentage in scores:
                user = self.bot.get_user(discord_user).display_name
                message = message + f"""\n{position}. {user} ({percentage}% - {score} hunts)"""

                position += 1
                if position > limit:
                    break
        else:
            message = message + "\n1. Literally no-one"

        message = message + "\n```"

        await ctx.send(message)

    @commands.Cog.listener('on_message')
    async def check_refresh(self, message: discord.message.Message):
        """
        Check whether or not the scouting tracker should be automatically refreshed
        """
        if not self.started or message.channel.id != self._channel.id:
            return

        if message.author.id == self.bot.user.id:
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        self._banter_count = self._banter_count + 1

        if self._banter_count > self.REFRESH_AFTER:
            await self._message.delete()
            self._message = await ctx.send(self.render())
            self._banter_count = 0

    def render(self) -> str:
        """
        Render the scouting manager template
        """
        template = pystache.render(self.template, {'hunts': self._hunts})
        return f"""{template}\nTo add an entry to this list, use the `f.add` command\n```f.add Erle - The Fringes ( 14.5  , 12.4 )\nf.add Giri -- The Fringes ( 14.5  , 12.4 ) (Scouter Name)```\n\nOnce the train has concluded, use `f.end` to log the time of completion."""

    def _log_action(self, action: str):
        """
        Log a scouting action
        """
        print(action)
        self._action_logs.append(action)

        if len(self._action_logs) > 15:
            del self._action_logs[0]

    def _author_check(self, author: discord.User) -> typing.Callable:
        """
        Check callback generator for confirmation prompts
        """
        def inner_check(message):
            return message.author == author
        return inner_check

    async def _update(self, ctx: commands.context.Context, content: typing.Optional[str] = None) -> None:
        """
        Update the scoreboard message
        """
        try:
            await self._message.edit(content=content or self.render())
        except discord.NotFound:
            self._log.warning("Scouting log has vanished! Re-creating")
            self._message = await ctx.send(content or self.render())

    def _reset(self) -> None:
        """
        Reset scouting data after a session has concluded
        """
        self.started = False

        self._previous_hunts = self._hunts.copy()
        self._hunts = self.HUNTS.copy()

        self._previous_message = self._message
        self._message = None
        self._previous_channel = self._channel
        self._channel = None
        self._previous_session = self._session
        self._session = None

        self._banter_count = 0

