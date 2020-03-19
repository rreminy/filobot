import asyncio
import random

import discord
from aiohttp import web

from filobot.filobot import bot, GAMES, hunt_manager, log
from filobot.models import Player
import filobot.utilities.worlds as worlds

import json

import logging
logger = logging.getLogger(__name__)

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


async def _process_data(data):
    if 'r' in data.keys(): # 'r' is only on hunts (rank)
        logger.debug(f"Processing {data['id']} as a hunt")
        await _process_hunt(data)
    elif 'duration' in data.keys(): # 'duration' is only on fates
        logger.debug(f"Processing {data['id']} as a fate")
        await _process_fate(data)
    else: # when all else fails
        logger.warning(f"Unable to determine {data['id']}")
        logger.warning(data)


async def _process_hunt(data):
    try:
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
        return

    if not alive:
        # TODO: Deaths
        return

    return await hunt_manager.on_find(world, hunt['Name'], xivhunt, int(data['i']) or 1)


async def _process_fate(data):
    # TODO
    return


async def discord_listener(channel):
    await bot.wait_until_ready()

    async def on_message(message):
        if str(message.channel.id) != channel:
            return;

        data = json.loads(message.content)
        await _process_data(data)
        return

    bot.add_listener(on_message)
    return


async def start_server(addr, port):
    async def event(request):
        data = await request.post()
        await _process_data(data)
        return web.Response(text='200')

    app = web.Application()
    app.router.add_route('POST', '/{tail:.*}', event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, addr, port)
    await site.start()


async def update_worlds():
    await bot.wait_until_ready()

    while not bot.is_closed():
        await worlds.do_update()
        await asyncio.sleep(1800.0)


async def track_stats():
    await bot.wait_until_ready()

    while not bot.is_closed():
        a_count, s_count = await hunt_manager.count()
        a_count = "{:,}".format(a_count)
        s_count = "{:,}".format(s_count)
        player_count = Player.select().where(Player.status == Player.STATUS_VERIFIED).count()
        player_count = "{:,}".format(player_count)

        s_stats = bot.get_channel(650987949026181120)  # type: discord.VoiceChannel
        await s_stats.edit(name=f"S-Rank relays: {s_count}")

        a_stats = bot.get_channel(650988270787756042)  # type: discord.VoiceChannel
        await a_stats.edit(name=f"A-Rank relays: {a_count}")

        verified_stats = bot.get_channel(650988353440972801)  # type: discord.VoiceChannel
        await verified_stats.edit(name=f"Verified members: {player_count}")

        await asyncio.sleep(1800.0)
