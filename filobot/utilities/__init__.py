import json
import os
import sys
import time
import arrow
import discord
import typing

with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json')) as json_file:
    marks_info = json.load(json_file)

COLOR_A = 0xFB6107
COLOR_S = 0xF3DE2C
COLOR_B = 0x7CB518

COLOR_OPEN      = 0x7CB518
COLOR_MAXED     = 0x275DAD
COLOR_DIED      = 0xFB6107
COLOR_CLOSED    = 0x5B616A

MAPS = {
    # The Lochs
    'Salt And Light': 'https://i.imgtc.com/1Zee4RA.png',            # S
    'Mahisha': 'https://i.imgtc.com/BCwWHco.png',                   # A
    'Luminare': 'https://i.imgtc.com/BCwWHco.png',                  # A
    'Kiwa': 'https://i.imgtc.com/ANGgY98.png',                      # B
    'Manes': 'https://i.imgtc.com/ANGgY98.png',                     # B

    # The Fringes
    'Udumbara': 'https://i.imgtc.com/hfm1lEx.png',                  # S
    'Orcus': 'https://i.imgtc.com/1LrMJ9l.png',                     # A
    'Erle': 'https://i.imgtc.com/1LrMJ9l.png',                      # A
    'Oezulem': 'https://i.imgtc.com/dIuffN3.png',                   # B
    'Shadow-Dweller Yamini': 'https://i.imgtc.com/dIuffN3.png',     # B

    # The Peaks
    'Bone Crawler': 'https://i.imgtc.com/qIYyQpr.png',              # S
    'Vochstein': 'https://i.imgtc.com/x3CqhLq.png',                 # A
    'Aqrabuamelu': 'https://i.imgtc.com/x3CqhLq.png',               # A
    'Buccaboo': 'https://i.imgtc.com/srFwFdZ.png',                  # B
    'Gwas-Y-Neidr': 'https://i.imgtc.com/srFwFdZ.png',              # B

    # The Azim Steppe
    'Orghana': 'https://i.imgtc.com/tzrfRth.png',                   # S
    'Girimekhala': 'https://i.imgtc.com/XYlb96U.png',               # A
    'Sum': 'https://i.imgtc.com/XYlb96U.png',                       # A
    'Aswang': 'https://i.imgtc.com/Xb7efhS.png',                    # B
    'Kurma': 'https://i.imgtc.com/Xb7efhS.png',                     # B

    # The Ruby Sea
    'Okina': 'https://i.imgtc.com/8oGlsHb.png',                     # S
    'Oni Yumemi': 'https://i.imgtc.com/VhK65N5.png',                # A
    'Funa Yurei': 'https://i.imgtc.com/VhK65N5.png',                # A
    'Guhuo Niao': 'https://i.imgtc.com/gRCD7jZ.png',                # B
    'Gauki Strongblade': 'https://i.imgtc.com/gRCD7jZ.png',         # B

    # Yanxia
    'Gamma': 'https://i.imgtc.com/QRyiPbp.png',                     # S
    'Gajasura': 'https://i.imgtc.com/nMFy37e.png',                  # A
    'Angada': 'https://i.imgtc.com/nMFy37e.png',                    # A
    'Gyorai Quickstrike': 'https://i.imgtc.com/dM4sjSQ.png',        # B
    'Deidar': 'https://i.imgtc.com/dM4sjSQ.png'                     # B
}

SB_HUNTS   = ['aqrabuamelu', 'vochstein', 'luminare', 'mahisha', 'funa yurei', 'oni yumemi', 'angada', 'gajasura', 'girimekhala']
SB_ALIASES = [('aqra', 'aqrabuamelu'), ('voch', 'vochstein'), ('lumi', 'luminare'), ('mahi', 'mahisha'),
           ('funa', 'funa yurei'), ('oni', 'oni yumemi'), ('anga', 'angada'), ('gaja', 'gajasura'),
           ('giri', 'girimekhala')]


def hunt_embed(hunt_name: str, horus: typing.Optional = None, xivhunt: typing.Optional = None) -> discord.Embed:
    for _id, mark in marks_info.items():
        if hunt_name.strip().lower() == mark['Name'].lower():
            embed = discord.Embed(title=mark['Name'], description=f"""Rank {mark['Rank']}""")
            embed.set_thumbnail(url=mark['Image'])

            # Default rank-based colors (overwritten if horus status is provided)
            if mark['Rank'] == 'A':
                embed.colour = COLOR_A
            elif mark['Rank'] == 'S':
                embed.colour = COLOR_S
            elif mark['Rank'] == 'B':
                embed.colour = COLOR_B

            embed.add_field(name='Zone', value=mark['ZoneName'])
            embed.add_field(name='Region', value=mark['RegionName'])

            # Only display spawning tips if the hunt is open
            if horus is None or horus.status in (horus.STATUS_OPENED, horus.STATUS_MAXED):
                if mark['SpawnTrigger']:
                    embed.add_field(name='Spawn trigger', value=mark['SpawnTrigger'])

                if mark['Tips']:
                    embed.add_field(name='Tips', value=mark['Tips'])

                # Don't show the map if the hunt location has already been found
                if xivhunt is None or not xivhunt['coords']:
                    if hunt_name.title() in MAPS:
                        embed.set_image(url=MAPS[hunt_name.title()])

            if horus is not None:
                # Horus status based color-coding
                if horus.status == horus.STATUS_OPENED:
                    embed.colour = COLOR_OPEN
                elif horus.status == horus.STATUS_MAXED:
                    embed.colour = COLOR_MAXED
                elif horus.status == horus.STATUS_DIED:
                    embed.colour = COLOR_DIED
                else:
                    embed.colour = COLOR_CLOSED

                embed.add_field(name='Status', value=horus.status.title(), inline=False)

                if horus.last_mark:
                    last_mark = arrow.get(horus.last_mark / 1000).format("MMM Do, H:mma ZZZ")
                    footer = f"""Marked {last_mark}"""
                    if horus.last_try_user != 'N/A':
                        footer = footer + f""" by {horus.last_try_user}"""
                    embed.set_footer(text=footer)

            if xivhunt is not None and xivhunt['coords']:
                embed.colour = COLOR_OPEN

                # Parse the time in a human friendly format
                hours, minutes = xivhunt['last_seen'].split(':')
                seconds = (int(hours) * 3600) + (int(minutes) * 60)
                ls_human = arrow.get(time.time() - seconds).format("MMM Do, H:mma ZZZ")

                embed.add_field(name='Last seen', value=ls_human)
                embed.add_field(name='Coords', value=xivhunt['coords'])

            return embed

    # No hunt by the specified name found
    raise KeyError


def parse_sb_hunt_name(hunt_name: str) -> str:
    """
    Parse an SB hunt name (offers support for hunt name aliases)
    """
    name = hunt_name.lower().strip()

    if name not in SB_HUNTS:
        # Shortened hunt name?
        for alias, replacement in SB_ALIASES:
            if name == alias:
                name = replacement
                break
        else:
            raise KeyError

    return name

