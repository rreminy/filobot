import asyncio
import random
import datetime
import time
import sys
import os
import json
import discord
import socketio
import aiohttp
import filobot.constants.zones as ZONES
import filobot.constants.datacenters as DATACENTERS
import filobot.utilities.worlds as worlds
import filobot.utilities.zones as zones
import logging
from aiohttp import web
from filobot.filobot import config, bot, GAMES, hunt_manager, log
from filobot.database.models import Player
from filobot.utilities.bear import BearHunt
from filobot.utilities.static_data import achievementfates_info
from filobot.utilities import parse_name
from filobot.utilities.worlds import Worlds
from filobot.notifications import notifications

logger = logging.getLogger(__name__)

huntQueue = {}

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
                    huntQueueCopy = huntQueue.copy()
                    for key, value in huntQueueCopy.items():
                        try:
                            if not isinstance(value, list) or len(value) < 2 or value[0] == None or value[1] == None:
                                #timestring = time.strftime("%H:%M:%S")
                                #print(f"{timestring} Removing hunt due to malformed data")
                                huntQueue.pop(key)
                                continue
                            data = value[0]
                            hunt = value[1]
                            if (int(time.time()) - hunt['last_seen']) > 240:
                                #timestring = time.strftime("%H:%M:%S")
                                #print(f"{timestring} Removing hunt due to being more than 4 minutes")
                                huntQueue.pop(key)
                                continue
                            if (int(time.time()) - hunt['last_seen']) >= 0:
                                #timestring = time.strftime("%H:%M:%S")
                                #print(f"{timestring} Releasing hunt due to reaching elapsed time")
                                await _process_data(source, data, None)
                        except Exception as e:
                            #print(f"Exception: {e}")
                            pass
                except Exception as e:
                    #timestring = time.strftime("%H:%M:%S")
                    #print(f"{timestring} Exception: {e}")
                    log.exception(f"Exception occurred in feed listener associated with {address}")
                    pass # TODO: Logging

# noinspection PyBroadException
async def bear_handler(self, data):
    try:
        if data is not None and type(data) == dict and len(data) > 1:
            if 'Notification' in data and data['Notification'] == "FoundReport" and 'Reporter' in data and data['Reporter'] != "" and 'World' in data:
                instance = int(data['Hunt'][-1]) if data['Hunt'][-2] == " " and data['Hunt'][-1].isdigit() else 0
                huntName = data['huntName'] if instance else data['huntName'][:-2]
                world = data['World']                
            if 'huntName' in data:
                instance = int(data['huntName'][-1]) if data['huntName'][-2] == " " and data['huntName'][-1].isdigit() else 0
                huntName = data['huntName'] if instance else data['huntName'][:-2]

                if huntName.lower() in hunt_manager.get_marks_info() and 'lastDeathTime' in data and 'expectMinTime' in data:
                    lastAlive = False if int(data['lastDeathTime']) > int(data['expectMinTime']) else True

                    if lastAlive:
                        bearHunt = await hunt_manager.bear.update_bear(data, hunt_manager.get_marks_info()[huntName.lower()], huntName, instance)

                        if bearHunt is not None:
                            await hunt_manager.recheck_trackers('FeedListener2', huntName, bearHunt, instance)
            if 'fateName' in data and 'completed' in data:
                progress = 100 if data['completed'] else 0
                instance = int(data['fateName'][-1]) if data['fateName'][-2] == " " and data['fateName'][-1].isdigit() else 1
                if progress == 100 and data['fateId'] in hunt_manager.bear.fates_info:
                    fateStruct = {
                        'progress': 100,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': data['worldName'],
                        'id': data['fateId'],
                        'state': 1,
                        'x': 1,
                        'y': 1,
                        'i': instance,
                        'lastReported': datetime.datetime.fromtimestamp(int((f"{data['lastDeath']}").split('.')[0][:-3]), datetime.timezone.utc).isoformat(),
                        'zoneID': f"{zones.id(hunt_manager.bear.fates_info[data['fateId']]['ZoneName'])}"
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

async def _process_data(source, data, message):
    marks_info = hunt_manager.bear.marks_info
    fates_info = hunt_manager.bear.fates_info

    try:
        if 'id' in data:
            if 'progress' in data and data['id'] in fates_info: # It's a FATE
                #logger.debug(f"Processing {data['id']} as a fate")
                await _process_fate(source, data)
            elif data['id'] in marks_info: # It's a hunt
                #logger.debug(f"Processing {data['id']} as a hunt")
                await _process_hunt(source, data)
            else: # when all else fails
                # logger.warning(f"Unable to determine {data}")
                pass
        elif message is not None:
            logger.debug(f"Received {message.content}")
            logger.debug(message.webhook_id)
            if message.webhook_id is not None and message.content.find("] S rank ") != -1:
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
        world   = Worlds.get_world_by_id(int(data['wId']))
        if world is None:
            return
        hunt    = hunt_manager.bear.id_to_hunt(data['id'])
        _plus   = 22.5 if hunt['ZoneName'] in ZONES.HW else 21.5
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
            'players': int(data["players"] if 'players' in data else 4),
            'hp': data["hp"] if "hp" in data else 100
        }

        # A hack to get the correct zone name
        zone = zones.name(data["zoneID"])
        hunt_manager.get_marks_info()[hunt['Name'].lower()]['ZoneName'] = zone
        hunt_manager.get_marks_info()[hunt['Name'].lower()]['ZoneID'] = int(data["zoneID"])

        if not alive:
            # TODO: Deaths
            return

        if hunt['Rank'] == "A":
           if xivhunt['players'] < 8 and xivhunt['zone_id'] > 494 and xivhunt['zone_id'] < 962:
              return
           if xivhunt['players'] < 9 and xivhunt['zone_id'] >= 962:
              return

        key = f"{world}_{parse_name(hunt['Name'])}_{i}"

        #if xivhunt['players'] == 0 and hunt['Rank'] == "S":
           #print(f"{hunt['Name']} on {world} has {xivhunt['players']} players")

        if hunt['Rank'] == "S" and int(float(xivhunt['hp'])) == 100 and 'Players' in hunt and xivhunt['players'] < hunt['Players'] and config.getboolean('Bot', 'PlayerActivityCheck'):
           datacenter = "Undecided"
           try:
              datacenter = worlds.Worlds.get_world_datacenter(world)
           except:
              log.exception('Exception thrown obtaining datacenter')
           #if xivhunt['players'] > 1:
              #print(f"{time.time()} :  {hunt['Name']} on {world} only has {xivhunt['players']} players")
           if datacenter != "Primal" and datacenter != "Dynamis" and datacenter != "Crystal" and datacenter != "Chaos":
              key = f"{world}_{parse_name(hunt['Name'])}_{i}"
              if key not in huntQueue:
                 if hunt['WaitTime'] != 0 and hunt['WaitTime'] != 1560:
                    huntQueue[key] = [data, xivhunt]
                    huntQueue[key][1]['last_seen'] = (int(time.time()) + hunt['WaitTime'])
                    #timestring = time.strftime("%H:%M:%S")
                    #print(f"{timestring} Added hunt to queue")
                 return
              else:
                 if (int(time.time()) - huntQueue[key][1]['last_seen']) < 0 or (int(time.time()) - huntQueue[key][1]['last_seen']) > 240:
                    return
                 #else:
                    #print('lastseens were the same, posting hunt')

        if key in huntQueue:
           #print(f"{key} {(huntQueue[key][1]['last_seen'] - int(time.time()))}")
           huntQueue.pop(key)
           #timestring = time.strftime("%H:%M:%S")
           #print(f"{timestring} Removed hunt from hunt queue")

        if hunt['Rank'] == "SS":
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
        logger.debug(f"Searching for S Rank at: {zone}")
        for mark in hunt_manager.get_marks_info().values():
            if mark['ZoneName'].lower() == zone.lower() and mark['Rank'] == "S":
                logger.debug(f"Found: {mark}")
                hunt = mark
                break
        if not hunt:
            return
        x, y    = message.content.split("(")[1].split(",")[0].strip(), message.content.split("(")[1].split(",")[1].split(")")[0].strip()
        i = message.content.split(")")[1].strip()
        i = int(i if i != "" else 1)
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
            'hp': 100,
            #'zone_id': int(data["zoneID"]), # chaoshunt doesn't have a zone_id but its determined below
        }

        # A hack to get the correct zone name
        hunt_manager.get_marks_info()[hunt['Name'].lower()]['ZoneName'] = zone
        hunt_manager.get_marks_info()[hunt['Name'].lower()]['ZoneID'] = zones.id(zone)
        xivhunt["zone_id"] = hunt_manager.get_marks_info()[hunt['Name'].lower()]['ZoneID']

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

        world   = data['world'] if 'world' in data and data['world'] is not None else Worlds.get_world_by_id(int(data[config.get(source, 'wId')]))
        if world is None:
            return
        fate    = hunt_manager.bear.id_to_fate(data[config.get(source, 'id')])
        _plus   = 22.5 if fate['ZoneName'] in ZONES.HW else 21.5
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
            'players': int(data["players"] if 'players' in data else 0)
        }

        # Fate key
        key = f"{world}_{fate}_{i}"
        fate_info = hunt_manager.get_fates_info()[fate['Name'].lower()]

        # Update interval
        progressUpdateInterval = 5
        if "ProgressUpdateInterval" in fate_info:
            progressUpdateInterval = fate_info["ProgressUpdateInterval"]

        # Variables
        startTimeEpoch = int(data['startTimeEpoch'])
        progress = int(int(data['progress']) / progressUpdateInterval) * progressUpdateInterval
        xivhunt["status"] = str(progress)

        # Rate limit updates
        if key in fate_start and fate_start[key] == startTimeEpoch: # Similar to hunt's Actor IDs, startTimeEpoch can be used similarly
            if key in fate_progress and fate_progress[key] == progress:
                return

        if str(fate['ID']) in achievementfates_info and (key not in fate_start or fate_start[key] != startTimeEpoch):
            #if progress <= 4 or progress > 40 or int(time_left / 60) < 8 or xivhunt['players'] < 1:
            if progress > 40 or int(time_left / 60) < 8 or (progress <= 11 and 'IgnoreProgress' in fate and fate['IgnoreProgress'] == False):
                return

        # Update rate limiting check values
        if startTimeEpoch > 0:
                fate_start[key] = startTimeEpoch
        fate_progress[key] = progress

        # A hack to get the correct zone name (each fate id is in a unique zone and position, so this should work)
        zone = zones.name(data["zoneID"])
        fate_info['ZoneName'] = zone
        fate_info['ZoneID'] = int(data["zoneID"])

        # Add missing duration to the fate information
        if (not 'Duration' in fate_info) or duration > hunt_manager.get_fates_info()[fate['Name'].lower()]['Duration']:
            hunt_manager.get_fates_info()[fate['Name'].lower()]['Duration'] = duration

    except:
        log.exception('Exception thrown') # for testing fates stuff
        return

    return await hunt_manager.on_find(world, fate['Name'], xivhunt, int(i) or 1)

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
