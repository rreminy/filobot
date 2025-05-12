import asyncio
from filobot.filobot import config, bot, hunts, fates
from filobot.tasks import update_game, update_hunts, update_fates, update_worlds, start_server, discord_listener, track_stats, feed_listener, auto_restart
import filobot.utilities.worlds as worlds

asyncio.run(worlds.init())

async def main():
    await bot.login(config.get('Bot', 'Token'))

    asyncio.create_task(update_hunts())
    asyncio.create_task(update_fates())
    asyncio.create_task(update_game())
    asyncio.create_task(update_worlds())
    asyncio.create_task(auto_restart())

    for i in range(1, 4):
        if config.get(f'WebhookServer{i}', 'Enabled') == 'TRUE':
            asyncio.create_task(start_server(f'WebhookServer{i}'))
        if config.get(f'WebhookDiscord{i}', 'Enabled') == 'TRUE':
            asyncio.create_task(discord_listener(f'WebhookDiscord{i}'))
        if config.get(f'FeedListener{i}', 'Enabled') == 'TRUE':
            asyncio.create_task(feed_listener(f'FeedListener{i}'))

    await bot.connect()

asyncio.run(main())
