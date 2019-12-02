import asyncio
import random

import discord
from aiohttp import web

from filobot.filobot import bot, GAMES, hunt_manager, log
from filobot.models import Player

# noinspection PyBroadException
async def update_hunts():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await hunt_manager.recheck()
        except Exception:
            log.exception('Exception thrown while reloading hunts')
        await asyncio.sleep(7.0)


# noinspection PyBroadException
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

        # Dead? No reason to continue.
        if not alive:
            return web.Response(text='200')

        await hunt_manager.on_find(world, hunt['Name'], xivhunt, int(data['i']) or 1)
        return web.Response(text='200')

    app = web.Application()
    app.router.add_route('POST', '/{tail:.*}', event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '108.170.28.204', 9544)
    await site.start()


async def track_stats():
    a_count, s_count = await hunt_manager.count()
    a_count = "{:,}".format(a_count)
    s_count = "{:,}".format(s_count)
    player_count = Player.select().where(Player.status == Player.STATUS_VERIFIED).count()
    player_count = "{:,}".format(player_count)

    s_stats = await bot.get_channel(650987949026181120)  # type: discord.VoiceChannel
    await s_stats.edit(name=f"S-Rank relays: {s_count}")

    a_stats = await bot.get_channel(650988270787756042)  # type: discord.VoiceChannel
    await a_stats.edit(name=f"A-Rank relays: {a_count}")

    verified_stats = await bot.get_channel(650988353440972801)  # type: discord.VoiceChannel
    await verified_stats.edit(name=f"Verified members: {player_count}")

    await asyncio.sleep(1800.0)
