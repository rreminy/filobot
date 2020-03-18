import os
import sys
import logging
import time
import csv

import asyncio
import aiohttp

# Constants
UPDATE_INTERVAL = 60 * 60 * 24 # 24 hours

# Logger
logger = logging.getLogger(__name__)
#logLevel = getattr(logging, 'DEBUG');
#logger.setLevel(logLevel)


# Globals
worlds = {
    'name': "Worlds",
    'file_path': os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'worlds.csv'),
    'url': 'https://raw.githubusercontent.com/xivapi/ffxiv-datamining/master/csv/World.csv',
    'last_updated': 0,
    'data': ""
}

datacenters = {
    'name': "Datacenters",
    'file_path': os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'datacenters.csv'),
    'url': 'https://raw.githubusercontent.com/xivapi/ffxiv-datamining/master/csv/WorldDCGroupType.csv',
    'last_updated': 0,
    'data': ""
}

def read_file(path):
    # Open the file
    logger.debug(f"Reading file: {path}")
    with open(path, 'rb') as file:
        # Read the file and return its contents
        return file.read().decode('utf-8')


def write_file(path, data):
    # Open the file
    logger.debug(f"Writing file: {path}")
    with open(path, 'wb') as file:
        # Write the data into the file
        return file.write(bytearray(data, 'utf-8'))


async def fetch(url):
    logger.debug(f"Fetching URL: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


async def update(obj):
    # Get the current system time
    cur_time = time.time()

    # Is the list updated? (Early check)
    if ((obj['last_updated'] + UPDATE_INTERVAL) > cur_time) and (obj['data'] != ""):
        # No need to update
        logger.debug(f"update(): {obj['name']} data is already up to date")
        return

    try:
        # Get the last modification time
        obj['last_updated'] = os.path.getmtime(obj['file_path'])

        # Read the file (do this early in case download fails)
        logger.debug(f"update(): Reading {obj['name']} data...")
        obj['data'] = read_file(obj['file_path'])

        # Is the list outdated?
        if ((obj['last_updated'] + UPDATE_INTERVAL) <= cur_time) or (obj['data'] == ""):
            raise Exception('Update needed')
    except:
        try:
            # Download list (fall-back)
            logger.debug(f"update(): Downloading {obj['name']} data...")
            obj['data'] = await fetch(obj['url'])

            try:
                # Write the data to the file
                logger.debug(f"update(): Saving {obj['name']} data...")
                write_file(obj['file_path'], obj['data'])
            except Exception as e:
                logger.warning(f"update(): Unable to save {obj['name']} data")
                logger.warning(e)

            # Set last modification time
            obj['last_updated'] = time.time()
        except:
            logger.warning(f"update(): Unable to download {obj['name']} data")

    # Is there data to begin with?
    if obj['data'] == "":
        logger.error(f"update(): {obj['name']} data unavailable!!")
        sys.exit(1)


# Process datacenters information
def process_datacenters():
    # ======================
    # Datacenters processing
    # ======================
    id_to_datacenter = {}
    datacenter_to_id = {}
    datacenter_worlds = {}
    datacenter_data = {}
    list = []

    logger.debug("Processing Datacenters data...")

    # Get datacenters data lines
    lines = datacenters['data'].split('\n');

    # First 3 lines are heading
    lines.pop(0)
    lines.pop(0)
    lines.pop(0)

    # Process each datacenter
    for line in lines:
        # Last line is empty...
        if (len(line) == 0):
            continue

        # Split CSV file fields
        field = line.split(',')

        # Fields to variables
        id = int(field[0])
        name = field[1][1:-1]
        region_id = int(field[2])

        # If invalid, just continue
        if region_id == 0:
            continue

        # Debug feedback
        logger.debug(f"{id} => {name} (Region ID: {region_id})")

        # Store the ID to Datacenter mapping
        id_to_datacenter[id] = name
        datacenter_to_id[name] = int(id)
        datacenter_worlds[name] = []
        datacenter_data[name] = {
            'id': id,
            'name': name,
            'region_id': region_id
        }
        list.append(name)

    # Store all information
    datacenters['id_to_datacenter'] = id_to_datacenter
    datacenters['id_to_dc'] = id_to_datacenter # alias

    datacenters['datacenter_to_id'] = datacenter_to_id
    datacenters['dc_to_id'] = datacenter_to_id # alias

    datacenters['datacenter_data'] = datacenter_data
    datacenters['dc_data'] = datacenter_data # alias

    datacenters['list'] = list


    # =================
    # Worlds processing
    # =================
    world_data = {}
    world_datacenter = {}
    id_to_world = {}
    list = []

    logger.debug("Processing worlds...")

    # Get worlds data lines
    lines = worlds['data'].split('\n')

    # First 3 lines are heading
    lines.pop(0)
    lines.pop(0)
    lines.pop(0)

    # Process each world
    for line in lines:
        # Last line is empty...
        if (len(line) == 0):
            continue

        # Split CSV file fields
        field = line.split(',')

        # Fields to variables
        id = int(field[0])
        name = field[1][1:-1]
        user_type = field[2] # Unused
        datacenter_id = int(field[3])
        public = True if field[4][0] == 'T' else False

        # If invalid or not public continue
        if (not public) or (datacenter_id == 0):
            continue

        # Get the world datacenter
        datacenter = datacenters['id_to_datacenter'][datacenter_id]

        # Debug feedback
        logger.debug(f"{name} => {datacenter} (id: {id})")

        # Store the mappings
        datacenter_worlds[datacenter].append(name)
        world_datacenter[name] = datacenter
        id_to_world[id] = name

        world_data[name] = {
            'id': id,
            'datacenter': datacenter
        }
        list.append(name)

    # Store all the information
    datacenters['datacenter_worlds'] = datacenter_worlds
    datacenters['dc_worlds'] = datacenter_worlds # alias

    worlds['datacenter_worlds'] = datacenter_worlds
    worlds['dc_worlds'] = datacenter_worlds # alias

    worlds['world_datacenter'] = world_datacenter
    worlds['world_dc'] = world_datacenter # alias

    worlds['id_to_world'] = id_to_world
    worlds['world_data'] = world_data

    worlds['list'] = list


def debug_print():
    logger.debug("Raw variable data")
    logger.debug("=================")

    logger.debug("datacenters:")
    logger.debug(datacenters)
    logger.debug("- - - - - - - - -")

    logger.debug("worlds:")
    logger.debug(worlds)
    logger.debug("=================")

    logger.debug(" ")
    logger.debug("Data Centers Worlds")
    logger.debug("===================")
    for (dc, _dc) in worlds['datacenter_worlds'].items():
        first = True
        output = dc + ": "
        for world in _dc:
            output += "" if first else ", "
            output += world
            first = False
        logger.debug(output)
    logger.debug("------------------")

    for (world, dc) in worlds['world_datacenter'].items():
        logger.debug(f"{world} => {dc}")


class Worlds:
    # Datacenters functions
    @staticmethod
    def get_datacenters():
        return datacenters['list']

    @staticmethod
    def get_datacenter_worlds(datacenter: str):
        return datacenters['datacenter_worlds'][datacenter]


    # Worlds functions
    @staticmethod
    def get_worlds():
        return worlds['list']

    @staticmethod
    def get_world_by_id(id: int):
        return worlds['id_to_world'][id]

    @staticmethod
    def get_world_datacenter(world: str):
        return worlds['world_datacenter'][world]


async def init():
    await asyncio.gather(update(datacenters), update(worlds))
    process_datacenters()
    debug_print()
