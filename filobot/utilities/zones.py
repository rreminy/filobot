from filobot.utilities.static_data import zones_info

info = zones_info

# Return zone struct by id or name, or return the entire list
def get(identifier = None):
    try:
        if identifier is None:
            return info
        elif isinstance(identifier, int) or identifier.isdigit():
            return info[identifier]
        elif isinstance(identifier, str):
            for zone in info.values():
                if zone['name'].lower() == identifier.lower():
                    return zone
            raise IndexError(f'No zone with the name {name} could be found')
        else:
            raise TypeError("Identifier must be an int (ID), str (name), or None")
    except KeyError:
        raise IndexError(f'No zone with the ID {identifier} could be found')

def id(name: str):
    try:
        for zone in info.values():
            if zone['name'].lower() == name.lower():
                return zone['id']
    except:
        raise IndexError(f'No zone with the name {name} could be found')

def name(id: int):
    try:
        return info[id]['name']
    except:
        raise IndexError(f'No zone with the ID {id} could be found')

def expansion(zone_id: int) -> str:
    expansions = [(211,"arr"),(354,"hw"),(494,"sb"),(956,"shb"),(962,"ew")]
    for threshold, expansion in expansions:
        if zone_id < threshold:
            return expansion
    return "dt"
