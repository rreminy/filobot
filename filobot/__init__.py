import asyncio
import logging
import typing
from configparser import ConfigParser
from discord.ext import commands
from filobot.Commands import Hunts
from filobot.utilities.manager import HuntManager

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

bot = commands.Bot(command_prefix='f.')
hunt_manager = HuntManager(bot)
bot.add_cog(Hunts(bot, hunt_manager))


@bot.event
async def on_ready():
    log.info(f"""Logged in as {bot.user.name} ({bot.user.id})""")

    print('Filo is ready for action!')
    print('------')


async def update_hunts():
    await bot.wait_until_ready()

    while not bot.is_closed():
        hunt_manager.recheck()
        await asyncio.sleep(15.0)

bot.loop.create_task(update_hunts())
