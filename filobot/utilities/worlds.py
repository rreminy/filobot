import logging

class Worlds:
    WORLDS = (
        'Adamantoise', 'Cactuar', 'Faerie', 'Gilgamesh', 'Jenova', 'Midgardsormr', 'Sargatanas', 'Siren',  # (NA) Aether
        'Behemoth', 'Excalibur', 'Exodus', 'Famfrit', 'Hyperion', 'Lamia', 'Leviathan', 'Ultros',  # (NA) Primal
        'Balmung', 'Brynhildr', 'Coeurl', 'Diabolos', 'Goblin', 'Malboro', 'Mateus', 'Zalera',  # (NA) Crystal

        'Cerberus', 'Louisoix', 'Moogle', 'Omega', 'Ragnarok', 'Spriggan',  # (EU) Chaos
        'Lich', 'Odin', 'Phoenix', 'Shiva', 'Twintania', 'Zodiark',  # (EU) Light

        'Aegis', 'Atomos', 'Carbuncle', 'Garuda', 'Gungnir', 'Kujata', 'Ramuh', 'Tonberry', 'Typhon', 'Unicorn', # (JP) Elemental
        'Alexander', 'Bahamut', 'Durandal', 'Fenrir', 'Ifrit', 'Ridill', 'Tiamat', 'Ultima', 'Valefor', 'Yojimbo', 'Zeromus', # (JP) Gaia
        'Anima', 'Asura', 'Belias', 'Chocobo', 'Hades', 'Ixion', 'Mandragora', 'Masamune', 'Pandaemonium', 'Shinryu', 'Titan' # (JP) Mana
    )

    DATACENTERS = {
        'Aether':  ('Adamantoise', 'Cactuar', 'Faerie', 'Gilgamesh', 'Jenova', 'Midgardsormr', 'Sargatanas', 'Siren'),
        'Primal':  ('Behemoth', 'Excalibur', 'Exodus', 'Famfrit', 'Hyperion', 'Lamia', 'Leviathan', 'Ultros'),
        'Crystal': ('Balmung', 'Brynhildr', 'Coeurl', 'Diabolos', 'Goblin', 'Malboro', 'Mateus', 'Zalera'),

        'Chaos':   ('Cerberus', 'Louisoix', 'Moogle', 'Omega', 'Ragnarok', 'Spriggan'),
        'Light':   ('Lich', 'Odin', 'Phoenix', 'Shiva', 'Twintania', 'Zodiark'),

        'Elemental': ('Aegis', 'Atomos', 'Carbuncle', 'Garuda', 'Gungnir', 'Kujata', 'Ramuh', 'Tonberry', 'Typhon', 'Unicorn'),
        'Gaia': ('Alexander', 'Bahamut', 'Durandal', 'Fenrir', 'Ifrit', 'Ridill', 'Tiamat', 'Ultima', 'Valefor', 'Yojimbo', 'Zeromus'),
        'Mana': ('Anima', 'Asura', 'Belias', 'Chocobo', 'Hades', 'Ixion', 'Mandragora', 'Masamune', 'Pandaemonium', 'Shinryu', 'Titan')
    }

    WORLD_DC = {}


    @staticmethod
    def init():
        Worlds._log = logging.getLogger("Worlds")
        Worlds.generate_world_dc()


    @staticmethod
    def generate_world_dc():
        for dc, worlds in DATACENTERS.items():
            for world in worlds:
                WORLD_DC[world] = dc
                Worlds._log.debug(f"Added world to dc mapping: {world} => {dc}")


Worlds.init()
