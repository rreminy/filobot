import asyncio
import random

import discord
from aiohttp import web

from filobot.filobot import bot, GAMES, hunt_manager, log


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

        await hunt_manager.on_find(world, hunt['Name'], xivhunt, int(data['i']) or 1)
        return web.Response(text='200')

    app = web.Application()
    app.router.add_route('POST', '/{tail:.*}', event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '108.170.28.204', 9544)
    await site.start()
