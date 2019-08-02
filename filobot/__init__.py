import asyncio
import logging
import traceback
import random
from configparser import ConfigParser
import discord
import math
from aiohttp import web

from discord.ext import commands
from filobot.Commands import Hunts
from filobot.Commands.admin import Admin
from filobot.Commands.ffxiv import FFXIV
from filobot.Commands.scouting import Scouting
from filobot.Commands.misc import Misc
from filobot.Commands.settings import Settings
from filobot.utilities.manager import HuntManager
from filobot.models import db, db_path, Subscriptions, SubscriptionsMeta, ScoutingSessions, ScoutingHunts, Player, \
    GuildSettings, KillLog

# Load our configuration
config = ConfigParser()
config.read(['config.default.ini', 'config.ini'])

# Set up logging
logLevel = getattr(logging, str(config.get('Server', 'LogLevel', fallback='ERROR')).upper())
logFormat = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")

log = logging.getLogger(__name__)
log.setLevel(logLevel)

ch = logging.StreamHandler()
ch.setLevel(logLevel)
ch.setFormatter(logFormat)

log.addHandler(ch)

db.create_tables([Subscriptions, SubscriptionsMeta, ScoutingSessions, ScoutingHunts, Player, GuildSettings, KillLog])

bot = commands.Bot(command_prefix='f.')
hunt_manager = HuntManager(bot)
bot.add_cog(Hunts(bot, hunt_manager))
bot.add_cog(Scouting(bot, hunt_manager))
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


# noinspection PyBroadException
async def update_hunts():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await hunt_manager.recheck()
        except Exception:
            log.exception('Exception thrown while reloading hunts')
        await asyncio.sleep(7.0)


async def update_game():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            game = random.choice(GAMES)
            await bot.change_presence(activity=discord.Game(name=game))
        except Exception:
            log.exception('Exception thrown while changing game status')
        await asyncio.sleep(60.0)


async def start_server():
    hunts = {}

    async def event(request):
        try:
            data    = await request.post()
            alive   = data['lastAlive'] == 'True'
            world   = hunt_manager.get_world(int(data['wId']))
            hunt    = hunt_manager.horus.id_to_hunt(data['id'])
            _plus   = 22.5 if hunt['ZoneName'] in hunt_manager.HW_ZONES else 21.5
            x, y    = round((float(data['x']) * 0.02 + _plus)*10)/10, round((float(data['y']) * 0.02 + _plus)*10)/10
            xivhunt = {
                'rank': data['r'],
                'status': 'seen' if alive else 'dead',
                'last_seen': data['lastReported'],
                'coords': f"{x}, {y}"
            }
        except IndexError:
            return web.Response(text='200')

        if world not in hunts:
            hunts[world] = {}

        # Dead? No reason to continue.
        if not alive:
            return web.Response(text='200')

        # Already seen? No reason to continue.
        if hunt['Name'] in hunts[world]:
            return web.Response(text='200')

        await hunt_manager.on_find(world, hunt['Name'], xivhunt, data['i'] or 1)
        return web.Response(text='200')

    app = web.Application()
    app.router.add_route('POST', '/{tail:.*}', event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '108.170.28.204', 9544)
    await site.start()

bot.loop.create_task(update_hunts())
bot.loop.create_task(update_game())
bot.loop.create_task(start_server())
