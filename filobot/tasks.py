import asyncio
import random
import datetime
import time
import sys
import os

import discord
from aiohttp import web
import aiohttp
import socketio

from filobot.filobot import config, bot, GAMES, hunt_manager, log
from filobot.models import Player
import filobot.utilities.worlds as worlds
from filobot.utilities.horus import HorusHunt

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
        await asyncio.sleep(15.0)

async def update_fates():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            await hunt_manager.check_fates()
        except Exception:
            log.exception('Exception thrown while checking fates')
        await asyncio.sleep(60.0)

# noinspection PyBroadException
async def feed_listener(source):
    address = config.get(source, "address")

    if 'bear' in address:
        try:
            dataCenters = list(hunt_manager.JA_DATACENTERS) + list(hunt_manager.EU_DATACENTERS) + list(hunt_manager.NA_DATACENTERS) + list(hunt_manager.OC_DATACENTERS)
            sessions = []

            for dataCenter in dataCenters:
                log.info(f"Connecting to bear for {dataCenter}")
                session = socketio.AsyncClient()
                await session.connect(address, namespaces='/HuntUpdate', socketio_path='/socket', retry=True)
                await session.emit('Change Room Request', dataCenter, namespace='/HuntUpdate')
                session.on('*', handler=bear_handler, namespace='/HuntUpdate')
                sessions.append(session)

            while not bot.is_closed():
                await asyncio.sleep(15.0) # Nothing to do anymore! But we can stall indefinitely until shutdown so we can disconnect properly

            for session in sessions:
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
                except Exception:
                    log.exception(f"Exception occurred in feed listener associated with {address}")
                    pass # TODO: Logging

# noinspection PyBroadException
async def bear_handler(self, data):
    try:
        if data is not None and type(data) == dict and len(data) > 1:
            if 'huntName' in data and data['huntName'].lower() in hunt_manager.getmarksinfo() and 'lastDeathTime' in data and 'expectMinTime' in data:
                lastAlive = False if int(data['lastDeathTime']) > int(data['expectMinTime']) else True

                if lastAlive:
                    horusHunt = await hunt_manager.horus.update_bear(data, hunt_manager.getmarksinfo()[data['huntName'].lower()])

                    if horusHunt is not None:
                        await hunt_manager.recheck_trackers('FeedListener2', data['huntName'], horusHunt, 0)
            if 'fateName' in data and 'completed' in data:
                progress = 100 if data['completed'] else 0

                if progress == 100 and data['fateId'] in hunt_manager.horus.fates_info:
                    fateStruct = {
                        'progress': 100,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': data['worldName'],
                        'id': data['fateId'],
                        'state': 1,
                        'x': 1,
                        'y': 1,
                        'i': 1,
                        'lastReported': data['lastDeath'].replace('T', ' ').split('.')[0],
                        'zoneID': str(hunt_manager.get_zone_id(hunt_manager.horus.fates_info[data['fateId']]['ZoneName'])),
                    }

                    await _process_data('FeedListener2', fateStruct, None)
    except:
        log.exception(data)
        log.exception("Exception occurred in feed listener associated with bear while processing last message")
        pass

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

huntInstance = dict()
chaosHunts = False
async def _process_data(source, data, message):
    marks_info = hunt_manager.horus.marks_info
    fates_info = hunt_manager.horus.fates_info
    global huntInstance
    global chaosHunts

    try:
        if 'id' in data:
            if 'progress' in data and data['id'] in fates_info: # It's a FATE
                #logger.debug(f"Processing {data['id']} as a fate")
                await _process_fate(source, data)
            elif data['id'] in marks_info: # It's a hunt
                if chaosHunts and marks_info[data['id']]['Rank'] == "S":
                    huntInstance[hunt_manager.get_world(int(data['wId'])) + '_' + marks_info[data['id']]['Name']] = data[config.get(source, 'i')] if config.get(source, 'i') in data else 0
                    return
                #logger.debug(f"Processing {data['id']} as a hunt")
                await _process_hunt(source, data)
            else: # when all else fails
                # logger.warning(f"Unable to determine {data}")
                pass
        elif message is not None:
            logger.debug(f"Received {message.content}")
            logger.debug(message.webhook_id)
            if message.webhook_id is not None and message.content.find("] S rank ") != -1:
                if not chaosHunts:
                    chaosHunts = True
                logger.debug(f"Processing message as a chaos hunt")
                await _process_chaoshunt(source, data, message)
        else:
            pass

    except:
        log.exception('Exception thrown') # for testing fates stuff
        return

async def _process_hunt(source, data):
    try:
        alive   = data['lastAlive'] == 'True'
        world   = hunt_manager.get_world(int(data['wId']))
        if world is None:
            return
        hunt    = hunt_manager.horus.id_to_hunt(data['id'])
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
            'x': x,
            'y': y,
            'zone_id': int(data["zoneID"]),
        }

        # A hack to get the correct zone name
        zone = hunt_manager.get_zone(data["zoneID"])
        hunt_manager._marks_info[hunt['Name'].lower()]['ZoneName'] = zone
        hunt_manager._marks_info[hunt['Name'].lower()]['ZoneID'] = int(data["zoneID"])

        if not alive:
            # TODO: Deaths
            return

        return await hunt_manager.on_find(world, hunt['Name'], xivhunt, int(i) or 1)

    except:
        log.exception('Exception thrown') # for testing fates stuff
        return


async def _process_chaoshunt(source, data, message):
    try:
        alive   = True
        world   = message.content.split("[")[1].split("]")[0]
        zone    = message.content.split("rank ")[1].split(",")[0].strip()
        hunt    = None
        for mark in hunt_manager._marks_info.values():
            logger.debug(mark)
            if mark['ZoneName'].lower() == zone.lower() and mark['Rank'] == "S":
                hunt = mark
                break
        if not hunt:
            return
        x, y    = message.content.split("(")[1].split(",")[0].strip(), message.content.split("(")[1].split(",")[1].split(")")[0].strip()
        i = huntInstance[world + '_' + hunt['Name']] if (world + '_' + hunt['Name']) in huntInstance else 1
        last_seen = int(time.time())
        xivhunt = {
            'rank': hunt['Rank'],
            'i': i, # data['i'], Seeing as this isn't functional anywhere at the moment
            'status': 'seen' if alive else 'dead',
            'last_seen': last_seen,
            'coords': f"{x}, {y}",
            'world': world,
            'x': x,
            'y': y,
            #'zone_id': int(data["zoneID"]), # chaoshunt doesn't have a zone_id but its determined below
        }

        # A hack to get the correct zone name
        hunt_manager._marks_info[hunt['Name'].lower()]['ZoneName'] = zone
        hunt_manager._marks_info[hunt['Name'].lower()]['ZoneID'] = hunt_manager.get_zone_id(zone)
        xivhunt["zone_id"] = hunt_manager._marks_info[hunt['Name'].lower()]['ZoneID']

        if not alive:
            # TODO: Deaths
            return

        return await hunt_manager.on_find(world, hunt['Name'], xivhunt, int(i) or 1)

    except:
        log.exception('Exception thrown') # for testing fates stuff
        return

fate_progress = dict()
fate_start = dict()
async def _process_fate(source, data):
    try:
        if (int(data['state']) == 255):
            return

        world   = data['world'] if 'world' in data and data['world'] is not None else hunt_manager.get_world(int(data[config.get(source, 'wId')]))
        if world is None:
            return
        fate    = hunt_manager.horus.id_to_fate(data[config.get(source, 'id')])
        _plus   = 22.5 if fate['ZoneName'] in hunt_manager.HW_ZONES else 21.5
        if config.get(source, 'x') == config.get(source, 'y'): # Some JSON structs use an array for X and Y
            data[config.get(source, 'x')] = data[config.get(source, 'x')]['x']
            data[config.get(source, 'y')] = data[config.get(source, 'y')]['y']
        x, y    = (data['x'], data['y']) if 'world' in data and data['world'] is not None else (round((float(data[config.get(source, 'x')]) * 0.02 + _plus)*10)/10, round((float(data[config.get(source, 'y')]) * 0.02 + _plus)*10)/10)
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
            'x': x,
            'y': y,
            'zone_id': int(data["zoneID"]),
        }

        # Fate key
        key = f"{world}_{fate}_{i}"
        fate_info = hunt_manager._fates_info[fate['Name'].lower()]

        # Update interval
        progressUpdateInterval = 5
        if "ProgressUpdateInterval" in fate_info:
            progressUpdateInterval = fate_info["ProgressUpdateInterval"]

        # Variables
        startTimeEpoch = int(data['startTimeEpoch'])
        progress = int(int(data['progress']) / progressUpdateInterval) * progressUpdateInterval
        if (progress > 90 and source == "FeedListener1"):
            return 
        xivhunt["status"] = str(progress)

        # Rate limit updates
        if key in fate_start and fate_start[key] == startTimeEpoch: # Similar to hunt's Actor IDs, startTimeEpoch can be used similarly
            if key in fate_progress and fate_progress[key] == progress:
                return

        # Update rate limiting check values
        if startTimeEpoch > 0:
                fate_start[key] = startTimeEpoch
        fate_progress[key] = progress

        # A hack to get the correct zone name (each fate id is in a unique zone and position, so this should work)
        zone = hunt_manager.get_zone(data["zoneID"])
        fate_info['ZoneName'] = zone
        fate_info['ZoneID'] = int(data["zoneID"])

        # Add missing duration to the fate information
        if (not 'Duration' in fate_info) or duration > hunt_manager._fates_info[fate['Name'].lower()]['Duration']:
            hunt_manager._fates_info[fate['Name'].lower()]['Duration'] = duration

    except:
        log.exception('Exception thrown') # for testing fates stuff
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

async def auto_restart():
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
