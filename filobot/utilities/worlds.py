import os, sys, logging, time, csv, asyncio, aiohttp

UPDATE_INTERVAL = 60 * 60 * 24 # 24 hours in seconds
logger = logging.getLogger(__name__)
_path_base = os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep

def get_last_update(obj):
    if obj['last_updated'] == 0:
        try:
            obj['last_updated'] = os.path.getmtime(obj['file_path'])
        except:
            return 0
    return obj['last_updated']

async def update_task(obj, force=False):
    if (time.time() > get_last_update(obj) + UPDATE_INTERVAL) and (obj['data'] != "") and (not force):
        return

    try:
        with open(obj['file_path'], 'rb') as file:
            obj['data'] = file.read().decode('utf-8')

        if (time.time() > get_last_update(obj) + UPDATE_INTERVAL) or (obj['data'] == "") or force:
            raise Exception('Update needed')
    except Exception:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(obj['url']) as response:
                    obj['data'] = await response.text()
            try:
                with open(obj['file_path'], 'wb') as file:
                    file.write(bytearray(obj['data'], 'utf-8'))
            except Exception:
                obj['last_updated'] = time.time()
        except Exception:
            logger.exception(f"update(): Unable to download {obj['name']} data")

    if obj['data'] == "":
        sys.exit(1)

dcs = {
    'name': "Datacenters",
    'file_path': _path_base + os.path.join('data', 'datacenters.csv'),
    'url': 'https://api.ffxivsonar.com/filo/datacenters',
    'last_updated': 0, 'data': ""
}

wlds = {
    'name': "Worlds",
    'file_path': _path_base + os.path.join('data', 'worlds.csv'),
    'url': 'https://api.ffxivsonar.com/filo/worlds',
    'last_updated': 0, 'data': ""
}

class Worlds:

    @classmethod
    async def init(self):
        try:
            return await self.update(Worlds())
        except Exception:
            logger.exception("Data processing failed!!")
            sys.exit(1)

    def get_datacenters(self):
        return dcs['list']

    def get_datacenters(self):
        return dcs['dc_worlds']

    # Get datacenter that world is on, or return a full list of worlds for a data center
    def get_datacenter(self, parameter: str):
        if parameter in wlds['world_dc']:
            return wlds['world_dc'][parameter]
        else:
            return dcs['dc_worlds'][parameter]

    def is_datacenter(self, datacenter: str):
        return True if datacenter in dcs['list'] else False

    def get_worlds(self):
        return wlds['list'] if 'list' in wlds else None

    def get_worlds_id(self):
        return wlds['world_to_id']

    def get_world(self, world):
        if isinstance(world, int) or isdigit(world):
            try:
                return wlds['id_to_world'][world]
            except:
                return None
        else:
            return wlds['world_to_id'][world]

    def is_world(self, world: str):
        return True if world in wlds['list'] else False

    async def update(self, force=False):
        for obj in [wlds, dcs]:
            if time.time() > get_last_update(obj) + UPDATE_INTERVAL:
                force = True
                break

        tasks, dcs['id_to_dc'], dcs['dc_to_id'], dcs['dc_worlds'], dcs['dc_data'], dcs['list'] = [], {}, {}, {}, {}, []

        for obj in [dcs, wlds]:
            tasks.append(asyncio.create_task(update_task(obj, force)))
        await asyncio.wait(tasks)

        lines = dcs['data'].split('\n')

        for i in range(0, 3):
            lines.pop(0)

        for line in lines:
            if (len(line) == 0):
                continue

            field = line.split(',')
            id, name, region_id = int(field[0]), field[1][1:-1], int(field[2])

            if region_id == 0:
                continue

            dcs['id_to_dc'][id], dcs['dc_to_id'][name], dcs['dc_worlds'][name] = name, int(id), []
            dcs['dc_data'][name] = {
                'id': id,
                'name': name,
                'region_id': region_id
            }
            dcs['list'].append(name)

        wlds['world_data'], wlds['world_dc'], wlds['id_to_world'], wlds['world_to_id'], wlds['list'], lines = {}, {}, {}, {}, [], wlds['data'].split('\n')

        for i in range(0, 3):
            lines.pop(0)

        for line in lines:
            if (len(line) == 0):
                continue

            field = line.split(',')

            id, name, dc_id, datacenter = int(field[0]), field[1][1:-1], int(field[5]), dcs['id_to_dc'][int(field[5])]
            public = True if field[6][0] == 'T' else False

            if (not public) or (dc_id == 0):
                continue

            dcs['dc_worlds'][datacenter].append(name)
            wlds['world_dc'][name], wlds['id_to_world'][id], wlds['world_to_id'][name] = datacenter, name, id
            wlds['world_data'][name] = {
                'id': id,
                'datacenter': datacenter
            }
            wlds['list'].append(name)

        wlds['dc_worlds'] = dcs['dc_worlds']

        return self

worlds = asyncio.run(Worlds.init())