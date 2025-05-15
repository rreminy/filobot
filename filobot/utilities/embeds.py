import arrow, discord, typing
from filobot.utilities.static_data import marks_info
from filobot.utilities.static_data import fates_info
from filobot.utilities.worlds import worlds
from filobot.utilities import parse_name

COLOR_A = 0xFB6107
COLOR_S = 0xF3DE2C
COLOR_B = 0x7CB518

COLOR_OPEN = 0x7CB518
COLOR_MAXED = 0x275DAD
COLOR_DIED = 0xFB6107
COLOR_CLOSED = 0x5B616A

def hunt_report_embed(hunt_name: str, tracked: typing.Optional = None, xivhunt: typing.Optional = None) -> discord.Embed:
    for _id, mark in marks_info.items():
        if parse_name(hunt_name) == mark['Name'].lower():
            embed = discord.Embed()

            world = xivhunt['world'] if xivhunt else None
            world = tracked.world if tracked else world

            if world and worlds.get_datacenter(world) in ('Elemental', 'Gaia', 'Mana', 'Meteor'):
                embed.title = f"Rankランク{mark['Rank']}: {mark['Name']}"
            else:
                embed.title = f"Rank {mark['Rank']}: {mark['Name']}"

            # Default rank-based colors (overwritten if tracker status is provided)
            if mark['Rank'] == 'A':
                embed.colour = COLOR_A
            elif mark['Rank'] == 'S' or mark['Rank'] == 'SS' or mark['Rank'] == 'SS Minion':
                embed.colour = COLOR_S
            elif mark['Rank'] == 'B':
                embed.colour = COLOR_B

            if tracked is not None:
                if tracked.status == tracked.STATUS_OPENED:
                    embed.colour = COLOR_OPEN
                elif tracked.status == tracked.STATUS_MAXED:
                    embed.colour = COLOR_MAXED
                elif tracked.status == tracked.STATUS_DIED:
                    embed.colour = COLOR_DIED
                    embed.title += " デッド " if world and worlds.get_datacenter(world) in ('Elemental', 'Gaia', 'Mana') else " "
                    embed.title += "DEAD"
                else:
                    embed.colour = COLOR_CLOSED
                    embed.title += " デッド " if world and worlds.get_datacenter(world) in ('Elemental', 'Gaia', 'Mana') else " "
                    embed.title += " DEAD"

            if xivhunt is not None:
                #if 'players' in xivhunt:
                    #embed.title += f" Players: {xivhunt['players']}"
                if mark['Rank'] == 'SS Minion' and 'zone_id' in xivhunt and xivhunt['zone_id'] <= 961:
                    embed.set_image(url=f"https://assets.ffxivsonar.com/ssminions/{xivhunt['zone_id']}.jpg")
                else:
                    embed.set_image(url=f"https://api.ffxivsonar.com/render/map?zoneid={xivhunt['zone_id']}&flagx={xivhunt['x']}&flagy={xivhunt['y']}")

                if 'hp' in xivhunt:
                    embed.title = f"{embed.title} {int(float(xivhunt['hp']))}%"
                    #embed.set_footer(text=f"HP Remaining: {xivhunt['hp']}%")

            return embed

def fate_report_embed(fate_name: str, xivhunt: typing.Optional = None) -> discord.Embed:
    for _id, fate in fates_info.items():
        if parse_name(fate_name) == fate['Name'].lower():
            embed = discord.Embed()

            if xivhunt is not None and xivhunt['status'] == 'alive':
                embed.colour = COLOR_OPEN
            else:
                embed.colour = COLOR_DIED

            if xivhunt is not None and xivhunt['world']:
                if worlds.get_datacenter(xivhunt['world']) in ('Elemental', 'Gaia', 'Mana', 'Meteor') and xivhunt['zone_id'] != 1237:
                    embed.title = f"[{xivhunt['world']}] {fate['NameJa']} {fate['Name']}"
                else:
                    embed.title = f"[{xivhunt['world']}] {fate['Name']}"

            else:
                embed.title = f"{fate['Name']}"

            if xivhunt is not None and xivhunt['zone_id'] != 1237 and xivhunt['zone_id'] != 886:
                embed.set_image(url=f"https://api.ffxivsonar.com/render/map?zoneid={xivhunt['zone_id']}&flagx={xivhunt['x']}&flagy={xivhunt['y']}&fate=true");

            return embed

def hunt_info_embed(hunt_name: str, tracked: typing.Optional = None, xivhunt: typing.Optional = None) -> discord.Embed:
    for _id, mark in marks_info.items():
        if parse_name(hunt_name) == mark['Name'].lower():
            embed = discord.Embed(title=mark['Name'], description=f"""Rank {mark['Rank']}""")
            embed.set_thumbnail(url=mark['Image'])

            # Default rank-based colors (overwritten if tracker status is provided)
            if mark['Rank'] == 'A':
                embed.colour = COLOR_A
            elif mark['Rank'] == 'S':
                embed.colour = COLOR_S
            elif mark['Rank'] == 'B':
                embed.colour = COLOR_B

            embed.add_field(name='Zone', value=mark['ZoneName'])
            embed.add_field(name='Region', value=mark['RegionName'])

            # Only display spawning tips if the hunt is open
            if tracked is None or tracked.status in (tracked.STATUS_OPENED, tracked.STATUS_MAXED):
                if mark['SpawnTrigger']:
                    embed.add_field(name='Spawn trigger', value=mark['SpawnTrigger'])

                if mark['Tips']:
                    embed.add_field(name='Tips', value=mark['Tips'])

                # Don't show the map if the hunt location has already been found
                if xivhunt is None or not xivhunt['coords']:
                    if hunt_name.title() in MAPS:
                        embed.set_image(url=MAPS[hunt_name.title()])

            if tracked is not None:
                # Tracker status based color-coding
                if tracked.status == tracked.STATUS_OPENED:
                    embed.colour = COLOR_OPEN
                elif tracked.status == tracked.STATUS_MAXED:
                    embed.colour = COLOR_MAXED
                elif tracked.status == tracked.STATUS_DIED:
                    embed.colour = COLOR_DIED
                else:
                    embed.colour = COLOR_CLOSED

                embed.add_field(name='Status', value=tracked.status.title(), inline=False)

                if tracked.last_mark:
                    last_mark = arrow.get(tracked.last_mark / 1000).format("MMM Do, H:mma ZZZ")
                    footer = f"""Marked {last_mark}"""
                    if tracked.last_try_user != 'N/A':
                        footer = footer + f""" by {tracked.last_try_user}"""
                    embed.set_footer(text=footer)

            return embed
    raise KeyError

def fate_info_embed(fate_name: str) -> discord.Embed:
    for _id, fate in fates_info.items():
        if parse_name(fate_name) == fate['Name'].lower():
            embed = discord.Embed(title=fate['Name'])
            embed.colour = COLOR_S
            embed.add_field(name='Zone', value=fate['ZoneName'])
            embed.add_field(name='Region', value=fate['RegionName'])

            # Only display spawning tips if the hunt is open
            if fate['SpawnTrigger']:
                embed.add_field(name='Spawn trigger', value=fate['SpawnTrigger'])

            if fate['Tips']:
                embed.add_field(name='Tips', value=fate['Tips'])

            return embed
    raise KeyError
