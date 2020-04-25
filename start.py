import asyncio
from filobot.filobot import config, bot
from filobot.tasks import update_game, update_hunts, update_worlds, start_server, discord_listener, track_stats
import filobot.utilities.worlds as worlds

# Initialize datacenters and worlds data
asyncio.run(worlds.init())

# Add bot tasks
bot.loop.create_task(update_hunts())
bot.loop.create_task(update_game())
bot.loop.create_task(track_stats())
bot.loop.create_task(update_worlds())

if config.get('WebhookServer1', 'Enabled') == 'TRUE':
    bot.loop.create_task(start_server('WebhookServer1'))

if config.get('WebhookServer2', 'Enabled') == 'TRUE':
    bot.loop.create_task(start_server('WebhookServer2'))

if config.get('WebhookServer3', 'Enabled') == 'TRUE':
    bot.loop.create_task(start_server('WebhookServer3'))

if config.get('WebhookDiscord1', 'Enabled') == 'TRUE':
    bot.loop.create_task(discord_listener('WebhookDiscord1'))

if config.get('WebhookDiscord2', 'Enabled') == 'TRUE':
    bot.loop.create_task(discord_listener('WebhookDiscord2'))

if config.get('WebhookDiscord3', 'Enabled') == 'TRUE':
    bot.loop.create_task(discord_listener('WebhookDiscord3'))

# Start the bot
bot.run(config.get('Bot', 'Token'))
