import asyncio
import logging
import os
import random
from configparser import ConfigParser
import discord

from discord.ext import commands
from filobot.Commands import Hunts
from filobot.Commands.admin import Admin
from filobot.Commands.scouting import Scouting
from filobot.utilities.manager import HuntManager
from filobot.models import db, db_path, Subscriptions, ScoutingSession, ScoutingHunts

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

if not os.path.isfile(db_path):
    log.info('Creating new database')
    db.create_tables([Subscriptions, ScoutingSession, ScoutingHunts])

bot = commands.Bot(command_prefix='f.')
hunt_manager = HuntManager(bot)
bot.add_cog(Hunts(bot, hunt_manager))
bot.add_cog(Scouting(bot, hunt_manager))
bot.add_cog(Admin(bot))


GAMES = ("with moogles", "in Totomo Omo's estate", "in the Izakaya Pub", "pranks on Joel Cleveland'", "with the hunt tracker")


@bot.event
async def on_ready():
    log.info(f"""Logged in as {bot.user.name} ({bot.user.id})""")

    print('Filo is ready for action!')
    print('------')


# noinspection PyBroadException
async def update_hunts():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await hunt_manager.recheck()
        except Exception:
            log.exception('Exception thrown while reloading hunts')
        await asyncio.sleep(15.0)


async def update_game():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            game = random.choice(GAMES)
            await bot.change_presence(activity=discord.Game(name=game))
        except Exception:
            log.exception('Exception thrown while changing game status')
        await asyncio.sleep(60.0)

bot.loop.create_task(update_hunts())
bot.loop.create_task(update_game())
