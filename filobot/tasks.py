import asyncio
import random
import time
import os
import json
import discord
import socketio
import aiohttp
import filobot.constants.datacenters as DATACENTERS
import filobot.utilities.worlds as worlds
import logging
from aiohttp import web
from filobot.filobot import config, bot, GAMES, notifications, tracker, hunts, fates, log
from filobot.database.models import Player
from filobot.tracker import bear_handler

logger = logging.getLogger(__name__)

async def update_hunts():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await hunts.recheck()
        except Exception:
            log.exception('Exception thrown while reloading hunts')
        await asyncio.sleep(15.0)

async def update_fates():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await fates.check_fates()
        except Exception:
            log.exception('Exception thrown while checking fates')
        await asyncio.sleep(60.0)

# noinspection PyBroadException
async def feed_listener(source):
    address = config.get(source, "address")

    if 'bear' in address:
        try:
            dataCenters = DATACENTERS.ALL

            session = socketio.AsyncClient()
            await session.connect(address, namespaces='/HuntUpdate', socketio_path='/socket', retry=True)
            await session.emit('Change Room Request', dataCenters, namespace='/HuntUpdate')
            session.on('*', handler=bear_handler, namespace='/HuntUpdate')

            while not bot.is_closed():
                await asyncio.sleep(15.0) # Stall indefinitely until shutdown

            session.disconnect()
        except Exception:
                log.exception(f"Exception occurred in feed listener associated with {address}")
                pass
    else:
        async with aiohttp.ClientSession() as session:
            while not bot.is_closed():
                await asyncio.sleep(15.0)
                try:
                    log.info(f"Connecting to {address}")
                    async with session.ws_connect(address) as ws:
                        async for msg in ws:
                            try:
                                data = json.loads(msg.data)
                                await _process_data(source, data, None)
                            except:
                                pass
                    hunt_queue = hunts.hunt_queue.copy()
                    for key, value in hunt_queue.items():
                        try:
                            if not isinstance(value, list) or len(value) < 2 or value[0] == None or value[1] == None:
                                hunts.hunt_queue.pop(key)
                                continue
                            data = value[0]
                            hunt = value[1]
                            if (int(time.time()) - hunt['last_seen']) > 240:
                                hunts.hunt_queue.pop(key)
                                continue
                            if (int(time.time()) - hunt['last_seen']) >= 0:
                                await _process_data(source, data, None)
                        except Exception as e:
                            pass
                except Exception as e:
                    log.exception(f"Exception occurred in feed listener associated with {address}")
                    pass # TODO: Logging

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

async def _process_data(source, data, message):
    marks_info = tracker.marks_info
    fates_info = tracker.fates_info

    try:
        if 'id' in data:
            if 'progress' in data and data['id'] in fates_info: # It's a FATE
                #logger.debug(f"Processing {data['id']} as a fate")
                await fates.process(source, data)
            elif data['id'] in marks_info: # It's a hunt
                #logger.debug(f"Processing {data['id']} as a hunt")
                await hunts.process(source, data)
            else: # when all else fails
                # logger.warning(f"Unable to determine {data}")
                pass
        elif message is not None:
            logger.debug(f"Received {message.content}")
            logger.debug(message.webhook_id)
            if message.webhook_id is not None and message.content.find("] S rank ") != -1:
                logger.debug(f"Processing message as a chaos hunt")
                await hunts.process_chaos(source, data, message)
        else:
            pass

    except:
        log.exception('Exception thrown') # for testing fates stuff
        return

async def discord_listener(source):
    await bot.wait_until_ready()

    async def on_message(message):
        if str(message.channel.id) != config.get(source, 'Channel'):
            return

        try:
            data = json.loads(message.content)
        except:
            data = dict()

        await _process_data(source, data, message)
        return

    bot.add_listener(on_message)
    return

async def start_server(source):
    async def event(request):
        data = json.loads(await request.post())
        if isinstance(data, list): # It's an array of JSON data... process one-by-one
            for x in data:
                await _process_data(source, x)
        else:
            await _process_data(source, data)
        return web.Response(text='200')

    app = web.Application()
    app.router.add_route('POST', '/{tail:.*}', event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.get(source, 'Address'), config.get(source, 'Port'))
    await site.start()

async def update_worlds():
    await bot.wait_until_ready()

    while not bot.is_closed():
        await worlds.do_update()
        await asyncio.sleep(1800.0)

async def track_stats():
    await bot.wait_until_ready()

    while not bot.is_closed():
        a_count, s_count = await notifications.count()
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

async def auto_restart():
    if config.getboolean('Bot', 'AutoRestart') == False:
        return

    RESTART_PERIOD = 60 * 60 * 24 * 3
    MINIMUM_THRESHOLD = 60 * 60 * 6

    current = time.time() % RESTART_PERIOD
    remaining = RESTART_PERIOD - current

    if remaining < MINIMUM_THRESHOLD:
        remaining = MINIMUM_THRESHOLD

    await asyncio.sleep(remaining)

    guild = bot.get_guild(477720463292891137) # Centurio Hunts

    if guild is not None:
        channel = guild.get_channel(597451395771138048) #mod-bot
        if channel is not None:
            try:
                await channel.send("All filo bots restarting, duplicate relays may happen during this period.")
            except:
                pass

    os._exit(1) # Why do I have to do this... sys.exit would had been better x.x
