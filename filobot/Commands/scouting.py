import os
import logging
import re
import sys
import arrow
import pystache
import discord
import typing

from discord.ext import commands
from filobot.utilities import hunt_embed
from filobot.utilities.horus import HorusHunt
from filobot.utilities.manager import HuntManager


class Scouting(commands.Cog):

    _message: typing.Optional[discord.Message]
    _previous_message: typing.Optional[discord.Message]

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

        self._hunts = self.HUNTS.copy()
        self.started = True

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

        hunt    = match.group('hunt').lower().strip()
        coords  = f"""( {match.group('coords')} )"""
        scout   = match.group('scout') or ctx.author.display_name
        scout   = scout[:30]

        if hunt not in self.HUNTS.keys():
            # Shortened hunt name?
            for alias, replacement in self.ALIASES:
                if hunt == alias:
                    hunt = replacement
                    break
            else:
                await ctx.message.delete()
                await ctx.send("Unknown hunt target: " + hunt, delete_after=10.0)
                return

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} scouted hunt target {hunt.title()} {coords} — {scout}"""
        self._log_action(_action)

        # Update hunt entry
        self._hunts[hunt] = {'loc': coords, 'scout': scout}
        await ctx.message.delete()
        await self._message.edit(content=self.render())

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

        scouts = "\n* ".join(scouts)
        scouts = f"""\n```markdown\nScouts: \n* {scouts}```""" if scouts else ''

        now = arrow.now().format("MMM Do, H:mma ZZZ")
        await self._message.edit(content=f"""Hunt session concluded **{now}**{scouts}""")
        self._reset()

        await ctx.message.delete()

    @commands.command()
    async def cancel(self, ctx: commands.context.Context):
        """
        Cancel a previously initialized scouting session
        """
        await self._message.delete()

        if not self.started:
            await ctx.send("There is no active scouting session to cancel.", delete_after=5.0)
            return

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
        self.started = True

        # Log the action
        _action = f"""{ctx.author.name}#{ctx.author.discriminator} restored a previous scouting session"""
        self._log_action(_action)

        await ctx.message.delete()
        await ctx.send("Scouting restored!", delete_after=5.0)
        await self._message.edit(content=self.render())

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

    def _reset(self) -> None:
        """
        Reset scouting data after a session has concluded
        """
        self.started = False

        self._previous_hunts = self._hunts.copy()
        self._hunts = self.HUNTS.copy()

        self._previous_message = self._message
        self._message = None

