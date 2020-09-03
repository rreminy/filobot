import asyncio
import random
import datetime
import time

import discord
from aiohttp import web

from filobot.filobot import config, bot, GAMES, hunt_manager, log
from filobot.models import Player
import filobot.utilities.worlds as worlds

import json

import logging
logger = logging.getLogger(__name__)


async def update_hunts():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await hunt_manager.recheck()
        except Exception:
            log.exception('Exception thrown while reloading hunts')
        await asyncio.sleep(7.0)

async def update_fates():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await hunt_manager.check_fates()
        except Exception:
            log.exception('Exception thrown while checking fates')
        await asyncio.sleep(60.0)

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
    marks_info = hunt_manager.horus.marks_info
    fates_info = hunt_manager.horus.fates_info
    if config.get(source, 'progress') in data and data[config.get(source, 'id')] in fates_info: # It's a FATE
        logger.debug(f"Processing {data['id']} as a fate")
        await _process_fate(source, data)
    elif data[config.get(source, 'id')] in marks_info: # It's a hunt
        logger.debug(f"Processing {data['id']} as a hunt")
        await _process_hunt(source, data)
    elif message.content.find("] S rank ") != -1:
        logger.debug(f"Processing {data['id']} as a chaos hunt")
        await _process_chaoshunt(source, data, message)
    else: # when all else fails
        logger.warning(f"Unable to determine {data['id']}")
        logger.warning(data)


async def _process_hunt(source, data):
    try:
        alive   = data[config.get(source, 'lastAlive')] == 'True'
        world   = hunt_manager.get_world(int(data[config.get(source, 'wId')]))
        hunt    = hunt_manager.horus.id_to_hunt(data[config.get(source, 'id')])
        _plus   = 22.5 if hunt['ZoneName'] in hunt_manager.HW_ZONES else 21.5
        if config.get(source, 'x') == config.get(source, 'y'): # Some JSON structs use an array for X and Y
            data[config.get(source, 'x')] = data[config.get(source, 'x')]['x']
            data[config.get(source, 'y')] = data[config.get(source, 'y')]['y']
        x, y    = round((float(data[config.get(source, 'x')]) * 0.02 + _plus)*10)/10, round((float(data[config.get(source, 'y')]) * 0.02 + _plus)*10)/10
        i = data[config.get(source, 'i')] if config.get(source, 'i') in data else 0
        lastreported = data[config.get(source, 'lastReported')]
        last_seen = datetime.datetime.fromisoformat(lastreported).timestamp()
        xivhunt = {
            'rank': hunt['Rank'],
            'i': i, # data['i'], Seeing as this isn't functional anywhere at the moment
            'status': 'seen' if alive else 'dead',
            'last_seen': last_seen,
            'coords': f"{x}, {y}",
            'world': world,
        }

        # A hack to get the correct zone name
        zone = hunt_manager.get_zone(data["zoneID"])
        hunt_manager._marks_info[hunt['Name'].lower()]['ZoneName'] = zone
        hunt_manager._marks_info[hunt['Name'].lower()]['ZoneID'] = int(data["zoneID"])

    except IndexError:
        return

    if not alive:
        # TODO: Deaths
        return

    return await hunt_manager.on_find(world, hunt['Name'], xivhunt, int(i) or 1)

async def _process_chaoshunt(source, data, message):
    try:
        alive   = True
        world   = message.content.split("[")[1].split("]")[0]
        zone    = message.content.split("rank ")[1].split(",")[0].strip()
        hunt    = None
        for mark in hunt_manager._marks_info.items():
            if mark['ZoneName'].lower() == zone.lower() and mark['Rank'] == "S":
                hunt = mark
                break
        if not hunt:
            return
        x, y    = data.split("(")[1].split(",")[0].strip(), data.split("(")[1].split(",")[1].split(")").strip()
        i = 1
        last_seen = int(time.time())
        xivhunt = {
            'rank': hunt['Rank'],
            'i': i, # data['i'], Seeing as this isn't functional anywhere at the moment
            'status': 'seen' if alive else 'dead',
            'last_seen': last_seen,
            'coords': f"{x}, {y}",
            'world': world,
        }

        # A hack to get the correct zone name
        hunt_manager._marks_info[hunt['Name'].lower()]['ZoneName'] = zone

    except IndexError:
        return

    if not alive:
        # TODO: Deaths
        return

    return await hunt_manager.on_find(world, hunt['Name'], xivhunt, int(i) or 1)


async def _process_fate(source, data):
    try:
        world   = hunt_manager.get_world(int(data[config.get(source, 'wId')]))
        fate    = hunt_manager.horus.id_to_fate(data[config.get(source, 'id')])
        _plus   = 22.5 if fate['ZoneName'] in hunt_manager.HW_ZONES else 21.5
        if config.get(source, 'x') == config.get(source, 'y'): # Some JSON structs use an array for X and Y
            data[config.get(source, 'x')] = data[config.get(source, 'x')]['x']
            data[config.get(source, 'y')] = data[config.get(source, 'y')]['y']
        x, y    = round((float(data[config.get(source, 'x')]) * 0.02 + _plus)*10)/10, round((float(data[config.get(source, 'y')]) * 0.02 + _plus)*10)/10
        i = data[config.get(source, 'i')] if config.get(source, 'i') in data else 0
        lastreported = data[config.get(source, 'lastReported')]
        last_seen = datetime.datetime.fromisoformat(lastreported).replace(tzinfo=datetime.timezone.utc).timestamp()
        startTimeEpoch = int(data['startTimeEpoch']) if 'startTimeEpoch' in data and data['startTimeEpoch'] and data['startTimeEpoch'].isnumeric() else 0
        duration = int(data['duration']) if 'duration' in data and data['duration'] and data['duration'].isnumeric() else 0
        time_left = (duration - (last_seen - startTimeEpoch)) if duration else -1
        logger.debug(f"time_left is {time_left}")
        xivhunt = { # Using this struct because the alternative is compatibility issues and endless copy & paste
            'rank': "F",
            'i': i, # data['i'], Seeing as this isn't functional anywhere at the moment
            'status': data[config.get(source, 'progress')],
            'last_seen': time_left, # hack by osc, reusing / repurposing the variable because its not being used anywhere else
            'coords': f"{x}, {y}",
            'world': world,
        }

        # A hack to get the correct zone name (each fate id is in a unique zone and position, so this should work)
        zone = hunt_manager.get_zone(data["zoneID"])
        hunt_manager._fates_info[fate['Name'].lower()]['ZoneName'] = zone
        hunt_manager._fates_info[fate['Name'].lower()]['ZoneID'] = int(data["zoneID"])

    except IndexError as e:
        log.exception('Exception thrown while reloading hunts') # for testing fates stuff
        return

    return await hunt_manager.on_find(world, fate['Name'], xivhunt, int(i) or 1)


async def discord_listener(source):
    await bot.wait_until_ready()

    async def on_message(message):
        #subs = await hunt_manager.get_subscriptions(message.channel.id)

        # This if shouldn't be ported to normal filo. It doesn't consider multiple discords like everything else does.
        # Prevents Filo reporting things if a user did it correctly already, so as not to undermine them.
        #if subs:
        #    #  Check worlds, but first check behemoth and odin, ixion, etc, then remove those from the list, so there's no clash
        #    world_name = None
        #    worldList = worlds.Worlds.get_worlds().copy()

        #    # These are both fates and world names, which complicates this.
        #    if message.content.lower().find("behe") >= 0:
        #        world_name = "Behemoth"

        #    if message.content.lower().find("odin") >= 0:
        #        world_name = "Odin"

        #    if message.content.lower().find("ixion") >= 0:
        #        world_name = "ixion"

        #    worldList.remove("Behemoth")
        #    worldList.remove("Odin")
        #    worldList.remove("Ixion")

        #    instance = 1

        #    if message.content.lower().find("i2") or message.content.lower().find("instance 2"):
        #        instance = 2
        #    if message.content.lower().find("i3") or message.content.lower().find("instance 3"):
        #        instance = 3

        #    for world in worldList:
        #        if message.content.lower().find(world.lower()[0:3]) >= 0:
        #            world_name = world

        #    if world_name:
        #        submetas = await hunt_manager.get_subscriptionsmetas(message.channel.id)

        #        for submeta in submetas:
        #            if submeta.value in message.role_mentions:
        #                if submeta.attachName == hunt_manager.SUB_TRAINS:
        #                    await hunt_manager.log_notification(message, message.channel_id, world_name, hunt_manager.SUB_TRAINS, instance)
        #                if submeta.attachName.lower() in hunt_manager.getmarksinfo().keys() or submeta.attachName.lower() in hunt_manager.getfatesinfo().keys():
        #                    hunt_manager._hunts[world]['xivhunt'].append(f"{submeta.attachName.strip().lower()}_{instance}")
        #                    await hunt_manager.log_notification(message, message.channel_id, world_name, submeta.attachName, instance)

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
        data = await request.post()
        if isinstance(data, list): # It's an array of JSON data... process one-by-one
            for x in data:
                await _process_data(source, x)
        else:
            await _process_data(source, data)
        return web.Response(text='200')

    await asyncio.sleep(20.0) # We don't want to bombard anyone's server (is this handled somewhere I'm not seeing?)

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
