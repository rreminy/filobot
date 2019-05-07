import os
import sys

import discord
import logging
import typing

from configparser import ConfigParser
from discord.ext import commands
from discord.ext.commands import CommandError
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

# if not os.path.isfile(db_path):
#     log.info('Creating new database')
#     db.create_tables([DiscordUser, Actions])

bot = commands.Bot(command_prefix='f.')
bot.add_cog(Hunts(bot, HuntManager(bot)))
# bot.add_cog(Utility(bot, config))
# bot.add_cog(Reactions(bot, config))


@bot.event
async def on_ready():
    log.info(f"""Logged in as {bot.user.name} ({bot.user.id})""")

    print('Filo is ready for action!')
    print('------')

