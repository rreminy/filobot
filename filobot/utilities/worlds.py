import os
import sys
import logging
import time
import csv

import asyncio
import aiohttp

# Constants
UPDATE_INTERVAL = 60 * 60 * 24 # 24 hours in seconds

# Logger
logger = logging.getLogger(__name__)


# Globals
_path_base = os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep
worlds = {
    'name': "Worlds",
    'file_path': _path_base + os.path.join('data', 'worlds.csv'),
    'url': 'https://raw.githubusercontent.com/xivapi/ffxiv-datamining/master/csv/World.csv',
    'last_updated': 0,
    'data': ""
}

datacenters = {
    'name': "Datacenters",
    'file_path': _path_base + os.path.join('data', 'datacenters.csv'),
    'url': 'https://raw.githubusercontent.com/xivapi/ffxiv-datamining/master/csv/WorldDCGroupType.csv',
    'last_updated': 0,
    'data': ""
}


def force_update_needed():
    # Check if anything is outdated
    for obj in [worlds, datacenters]:
        if time.time() > get_last_update(obj) + UPDATE_INTERVAL:
            return True
    return False


def update_needed_for(obj):
    # If data is empty then an update is needed
    if (obj['data'] == ""):
        return True

    # Check if its outdated
    if time.time() > get_last_update(obj) + UPDATE_INTERVAL:
        return True
    return False


def get_last_update(obj):
    # If last updated time is 0 then ... check it up
    if obj['last_updated'] == 0:
        try:
            obj['last_updated'] = os.path.getmtime(obj['file_path'])
        except:
            return 0

    # Return last updated time
    return obj['last_updated']


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


async def update(obj, force=False):
    # Is the list updated? (Early check)
    if (not update_needed_for(obj)) and (obj['data'] != "") and (not force):
        # No need to update
        logger.debug(f"update(): {obj['name']} data is already up to date")
        return

    try:
        # Read the file (do this early in case download fails)
        logger.debug(f"update(): Reading {obj['name']} data...")
        obj['data'] = read_file(obj['file_path'])

        # Is the list outdated?
        if update_needed_for(obj) or (obj['data'] == "") or force:
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
            except Exception:
                logger.exception(f"update(): Unable to save {obj['name']} data")

                # Sets the last updated time for the object
                obj['last_updated'] = time.time()
        except:
            logger.exception(f"update(): Unable to download {obj['name']} data")

    # Is there data to begin with?
    if obj['data'] == "":
        logger.exception(f"update(): {obj['name']} data unavailable!!")
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
    datacenter_list = []

    logger.debug("Processing Datacenters data...")

    # Get datacenters data lines
    lines = datacenters['data'].split('\n')

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
        datacenter_list.append(name)

    # Store all information
    datacenters['id_to_datacenter'] = id_to_datacenter
    datacenters['id_to_dc'] = id_to_datacenter # alias

    datacenters['datacenter_to_id'] = datacenter_to_id
    datacenters['dc_to_id'] = datacenter_to_id # alias

    datacenters['datacenter_data'] = datacenter_data
    datacenters['dc_data'] = datacenter_data # alias
    datacenters['list'] = datacenter_list

    # =================
    # Worlds processing
    # =================
    world_data = {}
    world_datacenter = {}
    id_to_world = {}
    world_to_id = {}
    datacenter_list = []

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
        # user_type = field[2] # Unused
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
        world_to_id[name] = id

        world_data[name] = {
            'id': id,
            'datacenter': datacenter
        }
        datacenter_list.append(name)

    # Store all the information
    datacenters['datacenter_worlds'] = datacenter_worlds
    datacenters['dc_worlds'] = datacenter_worlds # alias

    worlds['datacenter_worlds'] = datacenter_worlds # store in worlds too, because I'm dumb
    worlds['dc_worlds'] = datacenter_worlds # alias

    worlds['world_datacenter'] = world_datacenter
    worlds['world_dc'] = world_datacenter # alias

    worlds['id_to_world'] = id_to_world
    worlds['world_to_id'] = world_to_id

    worlds['world_data'] = world_data
    worlds['list'] = datacenter_list


async def do_update(force=False):
    # Debug feedback additional string
    forced_string = ""

    # Should updating be forced?
    if (force_update_needed()):
        forced_string = " (auto-forced)"
        force = True
    elif (force is True):
        forced_string = " (user-forced)"

    # Debug feedback
    logger.debug(f"Updating data{forced_string}...")

    # Setup update tasks
    tasks = []
    for obj in [datacenters, worlds]:
        tasks.append(update(obj, force))

    # Await all tasks and proccess all data
    await asyncio.wait(tasks)
    process_datacenters()


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


# The main class
class Worlds:
    # Datacenters functions
    @staticmethod
    def get_datacenters():
        return datacenters['list']

    @staticmethod
    def get_datacenters_worlds():
        return datacenters['datacenter_worlds']

    @staticmethod
    def get_datacenter_worlds(datacenter: str):
        return datacenters['datacenter_worlds'][datacenter]

    @staticmethod
    def is_datacenter(datacenter: str):
        return True if datacenter in datacenters['list'] else False

    # Worlds functions
    @staticmethod
    def get_worlds():
        return worlds['list']

    @staticmethod
    def get_worlds_id():
        return worlds['world_to_id']

    @staticmethod
    def get_world_id(world: str):
        return worlds['world_to_id'][world]

    @staticmethod
    def get_world_by_id(id: int):
        return worlds['id_to_world'][id]

    @staticmethod
    def get_world_datacenter(world: str):
        return worlds['world_datacenter'][world]

    @staticmethod
    def is_world(world: str):
        return True if world in worlds['list'] else False

    # Debugging functions (why would you want this...direct access)
    @staticmethod
    def debug_get_datacenters():
        return datacenters

    @staticmethod
    def debug_get_worlds():
        return worlds


async def init():
    # Update all the data
    try:
        await do_update()
    except Exception:
        logger.exception("Data processing failed!!")
        sys.exit(1)

    # Debug log the data (testing)
    debug_print()
