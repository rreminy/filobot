import asyncio
from filobot.filobot import config, bot
from filobot.tasks import update_game, update_hunts, start_server, discord_listener, track_stats
import filobot.utilities.worlds as worlds

# Bootstrap worlds
asyncio.run(worlds.init())

# Add bot tasks
bot.loop.create_task(update_hunts())
bot.loop.create_task(update_game())
bot.loop.create_task(track_stats())

if config.get('WebhookServer', 'Enabled') == 'TRUE':
    bot.loop.create_task(start_server(config.get('WebhookServer', 'Address'), config.get('WebhookServer', 'Port')))

if config.get('WebhookDiscord', 'Enabled') == 'TRUE':
    bot.loop.create_task(discord_listener(config.get('WebhookDiscord', 'Channel')))

# Start the bot
bot.run(config.get('Bot', 'Token'))
