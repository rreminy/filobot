import asyncio
from filobot.filobot import config, bot
from filobot.tasks import update_game, update_hunts, update_fates, update_worlds, start_server, discord_listener, track_stats, feed_listener, auto_restart
import filobot.utilities.worlds as worlds

# Initialize datacenters and worlds data
asyncio.run(worlds.init())

async def main():
    # Start the bot
    await bot.login(config.get('Bot', 'Token'))

    # Add bot tasks
    asyncio.create_task(update_hunts())
    asyncio.create_task(update_fates())
    asyncio.create_task(update_game())
    asyncio.create_task(update_worlds())
    asyncio.create_task(auto_restart())
    #asyncio.create_task(track_stats())

    if config.get('WebhookServer1', 'Enabled') == 'TRUE':
        asyncio.create_task(start_server('WebhookServer1'))

    if config.get('WebhookServer2', 'Enabled') == 'TRUE':
        asyncio.create_task(start_server('WebhookServer2'))

    if config.get('WebhookServer3', 'Enabled') == 'TRUE':
        asyncio.create_task(start_server('WebhookServer3'))

    if config.get('WebhookDiscord1', 'Enabled') == 'TRUE':
        asyncio.create_task(discord_listener('WebhookDiscord1'))

    if config.get('WebhookDiscord2', 'Enabled') == 'TRUE':
        asyncio.create_task(discord_listener('WebhookDiscord2'))

    if config.get('WebhookDiscord3', 'Enabled') == 'TRUE':
        asyncio.create_task(discord_listener('WebhookDiscord3'))

    if config.get('FeedListener1', 'Enabled') == 'TRUE':
        asyncio.create_task(feed_listener('FeedListener1'))

    if config.get('FeedListener2', 'Enabled') == 'TRUE':
        asyncio.create_task(feed_listener('FeedListener2'))

    if config.get('FeedListener3', 'Enabled') == 'TRUE':
        asyncio.create_task(feed_listener('FeedListener3'))

    await bot.connect()

asyncio.run(main())