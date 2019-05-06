import json
import os
import re
import logging
import sys
import discord
import typing

from configparser import ConfigParser
from discord.ext import commands
from discord.ext.commands import CommandError


class Hunts(commands.Cog):

    COLOR_A = 0xFB6107
    COLOR_S = 0xF3DE2C
    COLOR_B = 0x7CB518

    MAPS = {
        # The Lochs
        'Salt and Light': 'https://i.imgtc.com/1Zee4RA.png',            # S
        'Mahisha': 'https://i.imgtc.com/BCwWHco.png',                   # A
        'Luminare': 'https://i.imgtc.com/BCwWHco.png',                  # A
        'Kiwa': 'https://i.imgtc.com/ANGgY98.png',                      # B
        'Manes': 'https://i.imgtc.com/ANGgY98.png',                     # B

        # The Fringes
        'Udumbara': 'https://i.imgtc.com/hfm1lEx.png',                  # S
        'Orcus': 'https://i.imgtc.com/1LrMJ9l.png',                     # A
        'Erle': 'https://i.imgtc.com/1LrMJ9l.png',                      # A
        'Oezulem': 'https://i.imgtc.com/dIuffN3.png',                   # B
        'Shadow-dweller Yamini': 'https://i.imgtc.com/dIuffN3.png',     # B

        # The Peaks
        'Bone Crawler': 'https://i.imgtc.com/qIYyQpr.png',              # S
        'Vochstein': 'https://i.imgtc.com/x3CqhLq.png',                 # A
        'Aqrabuamelu': 'https://i.imgtc.com/x3CqhLq.png',               # A
        'Buccaboo': 'https://i.imgtc.com/srFwFdZ.png',                  # B
        'Gwas-y-neidr': 'https://i.imgtc.com/srFwFdZ.png',              # B

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

    def __init__(self, bot: discord.ext.commands.Bot, config: ConfigParser):
        self._log = logging.getLogger(__name__)
        self.bot = bot

        with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json')) as json_file:
            self.marks_info = json.load(json_file)

    @commands.command()
    async def info(self, ctx: commands.context.Context, *, name: str):
        """
        Return information on the specified hunt target
        """
        for _id, mark in self.marks_info.items():
            if name == mark['Name']:
                embed = discord.Embed(title=mark['Name'], description=f"""Rank {mark['Rank']}""")
                embed.set_thumbnail(url=mark['Image'])

                if name in self.MAPS:
                    embed.set_image(url=self.MAPS[name])

                if mark['Rank'] == 'A':
                    embed.colour = self.COLOR_A
                elif mark['Rank'] == 'S':
                    embed.colour = self.COLOR_S
                elif mark['Rank'] == 'B':
                    embed.colour = self.COLOR_B

                embed.add_field(name='Zone', value=mark['ZoneName'])
                embed.add_field(name='Region', value=mark['RegionName'])

                if mark['SpawnTrigger']:
                    embed.add_field(name='Spawn trigger', value=mark['SpawnTrigger'])

                if mark['Tips']:
                    embed.add_field(name='Tips', value=mark['Tips'])

                await ctx.send(embed=embed)
                return

        await ctx.send("No hunt by that name found - please check your spelling and try again")

    # @Commands.Cog.listener()
    # async def on_ready(self):
    #     # Loop through our active servers and make sure we're authorized
    #     for guild in self.bot.guilds:  # type: discord.guild.Guild
    #         if not self.server.authorized(guild.id):
    #             self._log.warning(f"""Unauthorized server: {guild.name} ({guild.id})""")
    #         else:
    #             self._log.info(f"""Connected to authorized server: {guild.name} ({guild.id})""")

    # async def cog_check(self, ctx: Commands.context.Context):
    #     if not self.server.authorized(ctx.guild.id):
    #         raise CommandError('This server is not authorized to use Nanachi!')
    #
    #     return True
