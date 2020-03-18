from filobot.filobot import config, bot
from filobot.tasks import update_game, update_hunts, start_server, discord_listener, track_stats

bot.loop.create_task(update_hunts())
bot.loop.create_task(update_game())
bot.loop.create_task(track_stats())

if config.get('WebhookServer', 'Enabled') == 'TRUE':
    bot.loop.create_task(start_server(config.get('WebhookServer', 'Address'), config.get('WebhookServer', 'Port')))

if config.get('WebhookDiscord', 'Enabled') == 'TRUE':
    bot.loop.create_task(discord_listener(config.get('WebhookDiscord', 'Channel')))

bot.run(config.get('Bot', 'Token'))
