import logging
import traceback
from configparser import ConfigParser

import discord
import math
from discord.ext import commands

from filobot.cogs import Hunts
from filobot.cogs.admin import Admin
from filobot.cogs.ffxiv import FFXIV
from filobot.cogs.misc import Misc
from filobot.cogs.settings import Settings
from filobot.models import db, GuildSettings, KillLog, Player, ScoutingHunts, ScoutingSessions, Subscriptions, \
    SubscriptionsMeta
from filobot.utilities.manager import HuntManager

# Load our configuration
config = ConfigParser()
config.read(['config.default.ini', 'config.ini'])

# Set up logging
logLevel = getattr(logging, str(config.get('Server', 'LogLevel', fallback='ERROR')).upper())
logFormat = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")

log = logging.getLogger('filobot')
log.setLevel(logLevel)

ch = logging.StreamHandler()
ch.setLevel(logLevel)
ch.setFormatter(logFormat)

log.addHandler(ch)

db.create_tables([Subscriptions, SubscriptionsMeta, ScoutingSessions, ScoutingHunts, Player, GuildSettings, KillLog])

bot = commands.Bot(command_prefix='f.')
hunt_manager = HuntManager(bot)
bot.add_cog(Hunts(bot, hunt_manager))
# bot.add_cog(Scouting(bot, hunt_manager))
bot.add_cog(FFXIV(bot, config.get('Bot', 'XivApiKey')))
bot.add_cog(Admin(bot))
bot.add_cog(Misc(bot, hunt_manager))
bot.add_cog(Settings(bot))


GAMES = ("with moogles", "in Totomo Omo's estate", "in the Izakaya Pub", "pranks on Joel Cleveland'", "with the hunt tracker")


@bot.event
async def on_ready():
    log.info(f"""Logged in as {bot.user.name} ({bot.user.id})""")

    print('Filo is ready for action!')
    print('------')


@bot.event
async def on_command_error(ctx: commands.context.Context, error: Exception):
    # if command has local error handler, return
    if hasattr(ctx.command, 'on_error'):
        return

    # get the original exception
    error = getattr(error, 'original', error)

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.BotMissingPermissions):
        missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_perms]
        if len(missing) > 2:
            fmt = '{}, and {}'.format("**, **".join(missing[:-1]), missing[-1])
        else:
            fmt = ' and '.join(missing)
        _message = 'I need the **{}** permission(s) to run this command.'.format(fmt)
        await ctx.send(_message)
        return

    if isinstance(error, commands.DisabledCommand):
        await ctx.send('This command has been disabled.')
        return

    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send("This command is on cooldown, please retry in {}s.".format(math.ceil(error.retry_after)))
        return

    if isinstance(error, commands.MissingPermissions):
        missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_perms]
        if len(missing) > 2:
            fmt = '{}, and {}'.format("**, **".join(missing[:-1]), missing[-1])
        else:
            fmt = ' and '.join(missing)
        _message = 'You need the **{}** permission(s) to use this command.'.format(fmt)
        await ctx.send(_message)
        return

    if isinstance(error, commands.UserInputError):
        await ctx.send("Invalid input. Please use `f.help` for instructions on how to use this command.")
        # await ctx.command.send_command_help(ctx) TODO
        return

    if isinstance(error, commands.NoPrivateMessage):
        try:
            await ctx.author.send('This command cannot be used in direct messages.')
        except discord.Forbidden:
            pass
        return

    if isinstance(error, discord.errors.Forbidden):
        log.warning(error)
        return

    if isinstance(error, commands.CheckFailure):
        await ctx.send("You do not have permission to use this command.")
        return

    # ignore all other exception types, but print them to stderr
    # noinspection PyBroadException
    try:
        channel_id = config.get('Bot', 'ChannelErrorLog', fallback=None)
        if channel_id:
            channel = ctx.bot.get_channel(int(channel_id))
            app_info = await ctx.bot.application_info()
            tb = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            await channel.send(content=f"{app_info.owner.mention} An exception has been logged:\n```\n{tb}\n```")
    except Exception:
        log.exception("Failed to log exception to the specified error logging channel")
        pass
    log.exception("An unknown exception occurred while executing a command", exc_info=error)
