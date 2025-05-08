import json
import logging
import os
import sys
import typing
import time
import asyncio
import aiohttp
import discord
import collections
from discord.ext import commands
from discord.utils import get
from discord import app_commands
from discord import Locale
from filobot.utilities import parse_name
from filobot.utilities.embeds import hunt_info_embed, fate_info_embed
from filobot.utilities.manager import HuntManager
from filobot.utilities.worlds import Worlds

class Hunts(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot, hunt_manager: HuntManager):
        self._log = logging.getLogger(__name__)
        self.bot = bot

        self.hunt_manager = hunt_manager

        self.srankPosts = {}

        self.arrSRanks = []
        self.hwSRanks = []
        self.sbSRanks = []
        self.shbSRanks = []
        self.ewSRanks = []

        for key, hunt in hunt_manager._marks_info.items():
            if hunt['ID'] < 4350 and hunt['Rank'] == 'S':
                self.arrSRanks.append(discord.SelectOption(label=hunt['Name'], value=hunt['ID']))
            elif hunt['ID'] < 5984 and hunt['Rank'] == 'S':
                self.hwSRanks.append(discord.SelectOption(label=hunt['Name'], value=hunt['ID']))
            elif hunt['ID'] < 8653 and hunt['Rank'] == 'S':
                self.sbSRanks.append(discord.SelectOption(label=hunt['Name'], value=hunt['ID']))
            elif hunt['ID'] < 10635 and hunt['Rank'] == 'S':
                self.shbSRanks.append(discord.SelectOption(label=hunt['Name'], value=hunt['ID']))
            elif hunt['ID'] > 10634 and hunt['Rank'] == 'S':
                self.ewSRanks.append(discord.SelectOption(label=hunt['Name'], value=hunt['ID']))

    async def send_report(type, worldId, huntOrFateId, instance, x, z):
        payload = {
            "Timestamp": int(time.time() * 1000),
            "X": x,
            "Y": 0,
            "Z": z
        }

        print(f"https://api.ffxivsonar.com/hint/killed/{type}/{worldId}_{huntOrFateId}_{instance}")
        print(payload)

        #async with aiohttp.ClientSession() as session:
        #    async with session.post(f"https://api.ffxivsonar.com/hint/killed/{type}/{worldId}_{huntOrFateId}_{instance}", json=payload) as response:
        #        if response.status == 200:
        #            print("Success:", await response.json())
        #        else:
        #            print("Failed:", response.status, await response.text())

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        try:
            channel = await self.bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            user = await self.bot.fetch_user(payload.user_id)
            emoji = payload.emoji
            if emoji.name == "DEAD" and message.author.id == self.bot.user.id and message.content.find("~~") < 0 and message.embeds[0]:
                worldId = Worlds.get_world_id(message.content[message.content.find("["):].split("]")[0].replace("[", ""))
                instance = 2 if message.content.find("②") > -1 else (3 if message.content.find("③") > -1 else 1)
                x, z = message.content.split("(")[1].split(")")[0].strip().split(",")
                if message.embeds[0].title.startswith("Rank"):
                     hunt = self.hunt_manager.getmarksinfo()[message.embeds[0].title[(message.embeds[0].title.find(":") + 2):].lower()]
                     payload = {
                         "Timestamp": int(time.time() * 1000),
                         "X": x,
                         "Y": 0,
                         "Z": z
                     }

                     #async with aiohttp.ClientSession() as session:
                     #     async with session.post(f"https://api.ffxivsonar.com/hint/killed/{'hunt'}/{worldId}_{hunt['ID']}_{instance}", json=payload) as response:
                     #         if response.status == 200:
                     #             print("Success:", await response.json())
                     #         else:
                     #             print("Failed:", response.status, await response.text())
                     #currently returns an error - temporary solution
                     await message.edit(content=(f"~~{message.content}~~"), embed=message.embeds[0])
                else:
                     #disable due to error
                     await message.edit(content=(f"~~{message.content}~~"), embed=message.embeds[0])
                     #for fate in self.hunt_manager.getfatesinfo():
                         #if message.embeds[0].title.find(fate['Name']) > -1:
                             #print(f"https://api.ffxivsonar.com/hint/killed/{'fate'}/{worldId}_{fate['ID']}_{instance}")
                             #await send_report("fate", worldId, fate['ID'], instance, x, z)
                             #break
        except Exception as e:
            print(e)

    @app_commands.command(name="info", description="Get information on a hunt or FATE")
    async def info(self, ctx: commands.context.Context, *, name: str):
        """
        Return information on the specified hunt or fate target
        """
        try:
            try:
                hunt_name = parse_name(name)
            except KeyError:
                hunt_name = name.lower().strip()

            try:
                embed = hunt_info_embed(name)
            except KeyError:
                try:
                    embed = fate_info_embed(name)
                except KeyError:
                    await ctx.response.send_message("No hunt or fate by that name found - please check your spelling and try again", ephemeral=True)
                    return

            await ctx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="about", description="Get information on a hunt or FATE")
    async def about(self, ctx: commands.context.Context, *, name: str):
        """
        Return information on the specified hunt or fate target
        """
        try:
            try:
                hunt_name = parse_name(name)
            except KeyError:
                hunt_name = name.lower().strip()

            try:
                embed = hunt_info_embed(name)
            except KeyError:
                try:
                    embed = fate_info_embed(name)
                except KeyError:
                    await ctx.response.send_message("No hunt or fate by that name found - please check your spelling and try again", ephemeral=True)
                    return

            await ctx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="commandlist", description="Get a list of commands")
    async def commandlist(self, ctx: commands.context.Context):
        """
        Return a list of commands
        """
        try:
            await ctx.response.send_message("/datacenter /world /about /info huntname /info fatename /relay srank /relay FATE /achievementFATE /srank /arank /mapparty /fatefarm /odin /steelreign /behemoth /preyonline /protoultima /coeurlregina /ixion /ahorseoutside /foxylady /tamamogozen /nothinglikeatrappinlife /formidable /archaeotania /chi /omicronrecall /daivadipa", ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="cmdlist", description="Get a list of commands")
    async def cmdlist(self, ctx: commands.context.Context):
        """
        Return a list of commands
        """
        try:
            await ctx.response.send_message("/datacenter /world /about /info huntname /info fatename /relay srank /relay FATE /achievementFATE /srank /arank /mapparty /fatefarm /odin /steelreign /behemoth /preyonline /protoultima /coeurlregina /ixion /ahorseoutside /foxylady /tamamogozen /nothinglikeatrappinlife /formidable /archaeotania /chi /omicronrecall /daivadipa", ephemeral=True)
        except Exception as e:
            print(e)

    relay = app_commands.Group(name="relay", description="Relay hunts or FATEs via paste")

    @relay.command(name="srank")
    async def relaySRank(self, ctx: commands.context.Context, *, paste: str, instance: int = 1) -> None:
        """
        Relay an S Rank via paste
        """
        debuginfo = ""
        try:
            for hunt in self.hunt_manager.getmarksinfo().values():
                debuginfo = "in for loop"
                if hunt['Zone'] in str(paste):
                    debuginfo = "in if statement"
                    x, y = paste.split("(")[1].split(")")[0].strip().split(",")
                    debuginfo = "done xy assignment"
                    for world in Worlds.get_worlds():
                        if paste.find(world):
                            debuginfo = "under paste.find()"
                            xivhunt = {
                                'rank': hunt['Rank'],
                                'i': instance,
                                'status': 'seen',
                                'last_seen': time.time(),
                                'coords': f"{x}, {y}",
                                'world': world,
                                'x': x,
                                'y': y,
                                'zone_id': int(data["zoneID"]),
                            }

                            self.hunt_manager._marks_info[hunt['Name'].lower()]['ZoneName'] = self.hunt_manager.get_zone(data["zoneID"])
                            self.hunt_manager._marks_info[hunt['Name'].lower()]['ZoneID'] = int(data["zoneID"])

                            await hunt_manager.on_find(world, hunt['Name'], xivhunt, 1)
        except Exception as e:
            await ctx.response.send_message("Could not extract information. Try to include the following info (does not support instances): World Area Name ( X, Y )", ephemeral=True)
            print(e)
            print(debuginfo)

    @relay.command(name="fate")
    async def relayFATE(self, ctx: commands.context.Context, *, paste: str, instance: int = 1) -> None:
        """
        Relay a FATE via paste
        """
        try:
            for fate in self.hunt_manager.getfatesinfo():
                if paste.find(fate['Zone']) > -1:
                    x, y = paste.split("(")[1].split(")")[0].strip().split(",")
                    for world in Worlds.get_worlds():
                        if paste.find(world):
                            fateStruct = {
                                'progress': 0,
                                'duration': 0,
                                'startTimeEpoch': 0,
                                'world': world,
                                'id': coordinates.value,
                                'state': 1,
                                'x': float(coordinates.name.split(',')[0]),
                                'y': float(coordinates.name.split(',')[1]),
                                'i': 1,
                                'lastReported': "2024-06-23 01:15:14",
                                'zoneID': str(fate['ZoneID']),
                            }

                            await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            await ctx.response.send_message("Could not extract information. Try to include the following info (does not support instances): World Area Name ( X, Y )", ephemeral=True)
            print(e)

    @app_commands.command(name="achievementfate", description="Report an achievement FATE")
    async def achievementFATE(self, ctx: commands.context.Context, *, name: str):
        """
        Return information on the specified hunt or fate target
        """
        try:
            if ctx.locale == "de":
                await ctx.response.send_message("Noch nicht implementiert." + datacenter.value, ephemeral=True)
            elif ctx.locale == "fr":
                await ctx.response.send_message("Pas encore implémenté.", ephemeral=True)
            elif ctx.locale == "ja":
                await ctx.response.send_message("まだ実装されていません。", ephemeral=True)
            else:
                await ctx.response.send_message("Not yet implemented.", ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="datacenter", description="Set your datacenter")
    @app_commands.describe(datacenter="The data center that you want to see channels for")
    @app_commands.choices(datacenter=[
        app_commands.Choice(name="Aether", value="Aether"),
        app_commands.Choice(name="Crystal", value="Crystal"),
        app_commands.Choice(name="Primal", value="Primal"),
        app_commands.Choice(name="Dynamis", value="Dynamis"),
        app_commands.Choice(name="Light", value="Light"),
        app_commands.Choice(name="Chaos", value="Chaos"),
        app_commands.Choice(name="Shadow", value="Shadow"),
        app_commands.Choice(name="Materia", value="Materia"),
        app_commands.Choice(name="Elemental", value="Elemental"),
        app_commands.Choice(name="Meteor", value="Meteor"),
        app_commands.Choice(name="Mana", value="Mana"),
        app_commands.Choice(name="Gaia", value="Gaia")
        ])
    async def datacenter(self, interaction: discord.Interaction, *, datacenter: app_commands.Choice[str]):
        # ctx: commands.context.Context
        """
        Return a list of commands
        """
        try:
            role = discord.utils.get(interaction.user.guild.roles, name=datacenter.value)
            action = "Added data center role "
            if role in interaction.user.roles:
                await interaction.user.remove_roles(discord.utils.get(interaction.user.guild.roles, name=datacenter.value))
                action = "Removed data center role "
            else:
                await interaction.user.add_roles(discord.utils.get(interaction.user.guild.roles, name=datacenter.value))
            if interaction.locale == "de":
                await interaction.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter.value, ephemeral=True)
            elif interaction.locale == "fr":
                await interaction.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter.value, ephemeral=True)
            elif interaction.locale == "ja":
                await interaction.response.send_message("データセンターの役割を追加 " + datacenter.value, ephemeral=True)
            else:
                await interaction.response.send_message(action + datacenter.value, ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="world", description="Set your world")
    @app_commands.describe(world="The world whose datacenter you want to see channels for")
    async def world(self, interaction: discord.Interaction, *, world: str):
        """
        Return a list of commands
        """
        try:
            datacenter = Worlds.get_world_datacenter(world)
            if datacenter is None or datacenter.find("Admin") > -1 or datacenter.find("Mod") > -1 or datacenter.find("_") > -1 or datacenter.find("Bot") > -1 or datacenter.find("nothing") > -1 or datacenter.find("Founder") > -1:
                await interaction.response.send_message("Failed", ephemeral=True)
                return
            role = discord.utils.get(interaction.user.guild.roles, name=datacenter)
            action = "Added data center role "
            if role in interaction.user.roles:
                await interaction.user.remove_roles(discord.utils.get(interaction.user.guild.roles, name=datacenter))
                action = "Removed data center role "
            else:
                await interaction.user.add_roles(discord.utils.get(interaction.user.guild.roles, name=datacenter))
            if interaction.locale == "de":
                await interaction.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
            elif interaction.locale == "fr":
                await interaction.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
            elif interaction.locale == "ja":
                await interaction.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
            else:
                await interaction.response.send_message(action + datacenter, ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="mapparty", description="Announce a map party.")
    @app_commands.describe(world="The world the treasure map party is on.")
    @app_commands.choices(type=[
        app_commands.Choice(name="Ophiotauroskin", value="Ophiotauroskin"),
        app_commands.Choice(name="Kumbhiraskin", value="Kumbhiraskin"),
        app_commands.Choice(name="Zonureskin", value="Zonureskin"),
        app_commands.Choice(name="Gazelleskin", value="Gazelleskin"),
        app_commands.Choice(name="Thief Map", value="Thief Map"),
        app_commands.Choice(name="Dragonskin", value="Dragonskin")
        ])
    @app_commands.choices(rules=[
        app_commands.Choice(name="FFA", value="FFA"),
        app_commands.Choice(name="Owner Needs, Rest Greed", value="Owner"),
        app_commands.Choice(name="Greed Only", value="Greed")
        ])
    @app_commands.describe(firstname="The first name of the character hosting the party.")
    @app_commands.describe(firstname="The second name of the character hosting the party.")
    async def mapparty(self, ctx: commands.context.Context, *, world: str, type: app_commands.Choice[str], rules: app_commands.Choice[str], firstname: str, secondname: str):
        """
        Announce a map party
        """
        try:
            #self.hunt_manager.mapParty(world, type.value, rules.value, firstname, lastname)
            #print("Not implemented yet.")
            #plan to do it via subscriptions, so that it restricts it to the right DC channel
            await ctx.response.send_message("Not yet implemented.", ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="fatefarm", description="Announce a FATE farm party.")
    @app_commands.describe(world="The world the FATE party is on.")
    @app_commands.describe(area="The area the FATE party is in.")
    @app_commands.choices(purpose=[
        app_commands.Choice(name="Shared FATE ranks", value="shared"),
        app_commands.Choice(name="Bicolor Gemstones", value="gemstone"),
        app_commands.Choice(name="Relic Weapon", value="relic"),
        app_commands.Choice(name="Leveling", value="leveling")
        ])
    @app_commands.describe(firstname="The first name of the character hosting the party.")
    @app_commands.describe(firstname="The second name of the character hosting the party.")
    async def fatefarm(self, ctx: commands.context.Context, *, world: str, area: str, purpose: app_commands.Choice[str], firstname: str, secondname: str):
        """
        Announce a FATE farm
        """
        try:
            #check area actually exists
            #self.hunt_manager.farmParty(world, area, purpose.value, firstname, lastname)
            #plan to do it via subscriptions, so that it restricts it to the right DC channel
            await ctx.response.send_message("Not yet implemented.", ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="odin", description="Announce that Odin spawned or toggle the role.")
    @app_commands.describe(world="The world that Odin is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="Location1")
        ])
    async def odin(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Odin spawned or toggle the role.
        """
        try:
            #if not world or not coordinates:
            #    await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="OdinFate"))
            #    if ctx.locale == "de":
            #        await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
            #    elif ctx.locale == "fr":
            #        await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
            #    elif ctx.locale == "ja":
            #        await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
            #    else:
            #        await ctx.response.send_message("Added OdinFate role", ephemeral=True)
            #else:
            #        fateStruct = {
            #            'progress': 0,
            #            'duration': 0,
            #            'startTimeEpoch': 0,
            #            'world': world,
            #            'id': coordinates.value,
            #            'state': 1,
            #            'x': float(coordinates.name.split(',')[0]),
            #            'y': float(coordinates.name.split(',')[1]),
            #            'i': 1,
            #            'lastReported': "2024-06-23 01:15:14",
            #            'zoneID': "53",
            #        }

            #        await _process_data('FeedListener1', fateStruct, None)
            await ctx.response.send_message("Not yet implemented. Use the OdinFate role manually!", ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="steelreign", description="Announce that Steel Reign spawned or toggle the role.")
    @app_commands.describe(world="The world that Steel Reign is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="Location1")
        ])
    async def steelreign(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Steel Reign spawned or toggle the role.
        """
        try:
            #if not world or not coordinates:
            #    await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="OdinFate"))
            #    if ctx.locale == "de":
            #        await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
            #    elif ctx.locale == "fr":
            #        await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
            #    elif ctx.locale == "ja":
            #        await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
            #    else:
            #        await ctx.response.send_message("Added OdinFate role", ephemeral=True)
            #else:
            #        #fateStruct = {
            #        #    'progress': 0,
            #        #    'duration': 0,
            #        #    'startTimeEpoch': 0,
            #        #    'world': world,
            #        #    'id': coordinates.value,
            #        #    'state': 1,
            #        #    'x': float(coordinates.name.split(',')[0]),
            #        #     'y': float(coordinates.name.split(',')[1]),
            #        #    'i': 1,
            #        #    'lastReported': "2024-06-23 01:15:14",
            #        #    'zoneID': "53",
            #        #}

            #        #await _process_data('FeedListener1', fateStruct, None)
            await ctx.response.send_message("Not yet implemented. Use the OdinFate role manually!", ephemeral=True)
        except Exception as e:
            print(e)

    @app_commands.command(name="behemoth", description="Announce that Behemoth spawned or toggle the role.")
    @app_commands.describe(world="The world that Odin is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="505"),
        app_commands.Choice(name="Location", value="506"),
        ])
    async def behemoth(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Behemoth spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="BehemothFate"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added BehemothFate role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': coordinates.value,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "53",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="preyonline", description="Announce that Prey Online spawned or toggle the role.")
    @app_commands.describe(world="The world that Prey Online is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="877"),
        app_commands.Choice(name="Location", value="878"),
        app_commands.Choice(name="Location", value="879")
        ])
    async def preyonline(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Prey Online spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="PreyOnline"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added PreyOnline role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': coordinates.value,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "216",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="protoultima", description="Announce that Prey Online spawned or toggle the role.")
    @app_commands.describe(world="The world that Prey Online is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="877"),
        app_commands.Choice(name="Location", value="878"),
        app_commands.Choice(name="Location", value="879")
        ])
    async def preyonline(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Prey Online spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="PreyOnline"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added PreyOnline role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': coordinates.value,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "216",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="coeurlregina", description="Announce that Coeurlregina spawned or toggle the role.")
    @app_commands.describe(world="The world that Coeurlregina is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="905"),
        app_commands.Choice(name="Location", value="906"),
        app_commands.Choice(name="Location", value="907")
        ])
    async def coeurlregina(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Coeurlregina spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="Coeurlregina"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added Coeurlregina role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': coordinates.value,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "212",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="ixion", description="Announce that Ixion spawned or toggle the role.")
    @app_commands.describe(world="The world that Ixion is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="1103"),
        app_commands.Choice(name="Location", value="1104"),
        app_commands.Choice(name="Location", value="1105")
        ])
    async def ixion(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Ixion spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="Ixion"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added Ixion role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': 907,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "369",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="ahorseoutside", description="Announce that A Horse Outside spawned or toggle the role.")
    @app_commands.describe(world="The world that A Horse Outside is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="1103"),
        app_commands.Choice(name="Location", value="1104"),
        app_commands.Choice(name="Location", value="1105")
        ])
    async def ahorseoutside(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that A Horse Outside spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="Ixion"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added Ixion role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': coordinates.value,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "369",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="foxylady", description="Announce that Foxy Lady spawned or toggle the role.")
    @app_commands.describe(world="The world that Foxy Lady is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="1106"),
        app_commands.Choice(name="Location", value="1107"),
        app_commands.Choice(name="Location", value="1108")
        ])
    async def foxylady(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Foxy lady spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="FoxyLady"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added FoxyLady role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': coordinates.value,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "354",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="tomamogozen", description="Announce that Tomamo Gozen spawned or toggle the role.")
    @app_commands.describe(world="The world that Tomamo Gozen is on.")
    @app_commands.choices(coordinates=[
        app_commands.Choice(name="Location", value="1106"),
        app_commands.Choice(name="Location", value="1107"),
        app_commands.Choice(name="Location", value="1108")
        ])
    async def tomamogozen(self, ctx: commands.context.Context, *, world: str, coordinates: app_commands.Choice[str]):
        """
        Announce that Tomamo Gozen spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="Tomamo Gozen"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added FoxyLady role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': coordinates.value,
                        'state': 1,
                        'x': float(coordinates.name.split(',')[0]),
                        'y': float(coordinates.name.split(',')[1]),
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "354",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="archaeotania", description="Announce that Archaeotania spawned or toggle the role.")
    @app_commands.describe(world="The world that Archaeotania is on.")
    async def archaeotania(self, ctx: commands.context.Context, *, world: str):
        """
        Announce that Archaeotania spawned or toggle the role.
        """
        try:
            if not world or not coordinates:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="Archaeotania"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added Archaeotania role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': 1432,
                        'state': 1,
                        'x': 27.1,
                        'y': 26.5,
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "496",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="formidable", description="Announce that Formidable spawned or toggle the role.")
    @app_commands.describe(world="The world that Formidable is on.")
    async def formidable(self, ctx: commands.context.Context, *, world: str):
        """
        Announce that Formidable spawned or toggle the role.
        """
        try:
            if not world:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="Formidable"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added Formidable role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': 1464,
                        'state': 1,
                        'x': 33.7,
                        'y': 21.3,
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "492",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="daivadipa", description="Announce that Daivadipa spawned or toggle the role.")
    @app_commands.describe(world="The world that Daivadipa is on.")
    async def daivadipa(self, ctx: commands.context.Context, *, world: str):
        """
        Announce that Daivadipa spawned or toggle the role.
        """
        try:
            if not world:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="Daivadipa"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added Daivadipa role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': 1763,
                        'state': 1,
                        'x': 9.3,
                        'y': 37.7,
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "957",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="chi", description="Announce that Chi spawned or toggle the role.")
    @app_commands.describe(world="The world that Chi is on.")
    async def chi(self, ctx: commands.context.Context, *, world: str):
        """
        Announce that Chi spawned or toggle the role.
        """
        try:
            if not world:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="ChiFate"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added ChiFate role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': 1855,
                        'state': 1,
                        'x': 34.5,
                        'y': 21.5,
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "960",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="omicronrecall", description="Announce that Chi spawned or toggle the role.")
    @app_commands.describe(world="The world that Chi is on.")
    async def omicronrecall(self, ctx: commands.context.Context, *, world: str):
        """
        Announce that Chi spawned or toggle the role.
        """
        try:
            if not world:
                await ctx.author.add_roles(discord.utils.get(ctx.author.server.roles, name="ChiFate"))
                if ctx.locale == "de":
                    await ctx.response.send_message("Rechenzentrumsrolle hinzugefügt " + datacenter, ephemeral=True)
                elif ctx.locale == "fr":
                    await ctx.response.send_message("Ajout de l'autorisation de rôle du centre de données " + datacenter, ephemeral=True)
                elif ctx.locale == "ja":
                    await ctx.response.send_message("データセンターの役割を追加 " + datacenter, ephemeral=True)
                else:
                    await ctx.response.send_message("Added ChiFate role", ephemeral=True)
            else:
                    fateStruct = {
                        'progress': 0,
                        'duration': 0,
                        'startTimeEpoch': 0,
                        'world': world,
                        'id': 1855,
                        'state': 1,
                        'x': 34.5,
                        'y': 21.5,
                        'i': 1,
                        'lastReported': "2024-06-23 01:15:14",
                        'zoneID': "960",
                    }

                    await _process_data('FeedListener1', fateStruct, None)
        except Exception as e:
            print(e)

    @app_commands.command(name="srank", description="Report an S rank")
    @app_commands.describe(world="The world server the hunt is on")
    @app_commands.choices(level=[
        app_commands.Choice(name="50 - ARR", value=50),
        app_commands.Choice(name="60 - Heavensward", value=60),
        app_commands.Choice(name="70 - Stormblood", value=70),
        app_commands.Choice(name="80 - Shadowbringers", value=80),
        app_commands.Choice(name="90 - Endwalker", value=90)
        ])
    @app_commands.describe(level="The level/expansion of the hunt")
    async def srank(self, ctx: commands.context.Context, *, world: str, level: app_commands.Choice[int]):
        try:
            if not world or not level:
                hunt_name = parse_name(hunt_name)
                embed = hunt_info_embed(hunt_name)
                await ctx.response.send_message(embed=embed, ephemeral=True)
                return

            if level.value == 50:
                await ctx.response.send_message(ephemeral=True, view=SRankInteraction(self.arrSRanks, 'Select which level 50 S rank it is')) #, "button2"))
            elif level.value == 60:
                await ctx.response.send_message(ephemeral=True, view=SRankInteraction(self.hwSRanks, 'Select which level 60 S rank it is')) #, "button1"))
            elif level.value == 70:
                await ctx.response.send_message(ephemeral=True, view=SRankInteraction(self.sbSRanks, 'Select which level 60 S rank it is')) #, "button1"))
            elif level.value == 80:
                await ctx.response.send_message(ephemeral=True, view=SRankInteraction(self.shbSRanks, 'Select which level 60 S rank it is')) #, "button1"))
            elif level.value == 90:
                await ctx.response.send_message(ephemeral=True, view=SRankInteraction(self.ewSRanks, 'Select which level 60 S rank it is')) #, "button1"))
            else:
                await ctx.response.send_message(str(level.value) + "\n" + world, ephemeral=True)
        except Exception as e:
            print(e)

    @commands.command()
    async def status(self, ctx: commands.context.Context, world: str, hunt_name: str, instance: int = 1):
        """
        Retrieve the status of the specified hunt target
        """
        # Make sure the world is properly formatted
        world = world.strip().lower().title()
        try:
            hunt_name = parse_name(hunt_name)
        except KeyError:
            hunt_name = hunt_name.lower().strip()

        if instance < 1 or instance > 3:
            await ctx.reply("Invalid instance provided - please use a number between 1 and 3")
            return

        try:
            horus = self.hunt_manager.get(world, hunt_name, instance)
            embed = hunt_info_embed(hunt_name, horus)
        except KeyError as e:
            self._log.info(e)
            await ctx.reply("No world or hunt by that name found - please check your spelling and try again")
            return

        await ctx.reply(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def notify(self, ctx: commands.context.Context, role: typing.Union[discord.Role, str, None], attachname: typing.Optional[str]):
        """
        Adds a role to mention when something is found in this channel
        """
        if not role:
            await self.hunt_manager.remove_notifier(ctx.channel.id)
            await ctx.reply("Channel notifiers cleared.")
            return

        if type(role) is str:
            role = role.strip("`")
            role = get(guild.roles, name=role)

            if not role:
                await ctx.reply("Role does not exist.")
                return

        if attachname is not None:
            found = False
            attachname = attachname.strip().lower()

            if attachname in self.hunt_manager.HUNT_SUBSCRIPTIONS or attachname == "trains":
                found = True

            for fate in self.hunt_manager.getfatesinfo().keys():
                if fate.find(attachname) > -1:
                    attachname = fate
                    found = True
                    break
            for hunt in self.hunt_manager.getmarksinfo().keys():
                if hunt.find(attachname) > -1:
                    attachname = hunt
                    found = True
                    break
            if not found:
                await ctx.send("Cannot find hunt or fate name.")
                return

        await self.hunt_manager.set_notifier(ctx.channel.id, role, attachname)

        await ctx.reply(f"Members of this role will now be notified whenever {'something' if not attachname else attachname.title()} is found in this channel. To undo this, run the notify command again without any arguments")

    @commands.command(name='sub-notify')
    @commands.has_permissions(administrator=True)
    async def sub_notify(self, ctx: commands.context.Context, role: typing.Union[discord.Role, str, None], attachname: typing.Optional[str]):
        """
        Adds a role to mention when something is found in this channel
        """

        if not role:
            await self.hunt_manager.remove_notifier(ctx.channel.id)
            await ctx.reply("Channel notifiers cleared.")
            return

        if type(role) is str:
            role = role.strip("`")
            role = get(guild.roles, name=role)

            if not role:
                await ctx.reply("Role does not exist.")
                return

        if attachname is not None:
            found = False
            attachname = attachname.strip().lower()

            if attachname in self.hunt_manager.HUNT_SUBSCRIPTIONS or attachname == "trains" or attachname == "blu_spell":
                found = True

            for fate in self.hunt_manager.getfatesinfo().keys():
                if fate.find(attachname) > -1:
                    attachname = fate
                    found = True
                    break
            for hunt in self.hunt_manager.getmarksinfo().keys():
                if hunt.find(attachname) > -1:
                    attachname = hunt
                    found = True
                    break
            if not found:
                await ctx.reply("Cannot find hunt or fate name.")
                return

        await self.hunt_manager.set_notifier(ctx.channel.id, role, attachname)

        await ctx.reply(f"Members of this role will now be notified whenever {'something' if not attachname else attachname.title()} is found in this channel. To undo this, run the notify command again without any arguments")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def sub(self, ctx: commands.context.Context, world: str, category: str, *, conditions: typing.Optional[str] = 'FINDS, DEATHS'):
        """
        Subscribe the channel to hunt and fate events
        Allowed categories: EW_A, EW_S, SHB_A, SHB_S, SB_A, SB_S, HW_A, HW_S, ARR_A, ARR_S, FATE, TRAINS
        Allowed conditions: FINDS, DEATHS, OPENINGS
        """
        message = await self.hunt_manager.subscribe(ctx.channel.id, world, category, conditions)
        if message:
            await ctx.send(message, delete_after=10.0)
        await ctx.message.delete()

    @commands.command(name='sub-all')
    @commands.has_permissions(administrator=True)
    async def sub_all(self, ctx: commands.context.Context, datacenter: str, category: str, *, conditions: typing.Optional[str] = 'FINDS, DEATHS'):
        """
        Subscribe the channel to hunt and fate events on ALL of a datacenters worlds
        Allowed datacenters: Elemental, Gaia, Mana, Aether, Primal, Crystal, Chaos, Light, Materia
        Allowed categories: EW_A, EW_S, SHB_A, SHB_S, SB_A, SB_S, HW_A, HW_S, ARR_A, ARR_S, FATE, TRAINS
        Allowed conditions: FINDS, DEATHS, OPENINGS
        """
        message = await self.hunt_manager.subscribe_all(datacenter, ctx.channel.id, category, conditions)
        if message:
            await ctx.send(message, delete_after=10.0)
        await ctx.message.delete()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unsub(self, ctx: commands.context.Context, world: str, category: str):
        """
        Unsubscribe the channel from hunt and fate events
        Allowed categories: EW_A, EW_S, SHB_A, SHB_S, SB_A, SB_S, HW_A, HW_S, ARR_A, ARR_S, FATE, TRAINS
        """
        message = await self.hunt_manager.unsubscribe(ctx.channel.id, world, category)
        if message:
            await ctx.send(message, delete_after=10.0)
        await ctx.message.delete()

    @commands.command(name='sub-list')
    @commands.has_permissions(administrator=True)
    async def sub_list(self, ctx: commands.context.Context):
        """
        List all enabled subscriptions for this channel
        """
        subs = await self.hunt_manager.get_subscriptions(ctx.channel.id)

        if not subs:
            await ctx.channel.reply("No subscriptions have been specified for this channel")
            return

        message = ''
        counter = 0
        i = 0
        for sub in subs:
            message = message + f"""\n* {sub.world} — {str(sub.category).upper().replace('_', ' ')} — {sub.event}"""
            i += 1
            counter += 1
            if i > 39:
                await ctx.send("```markdown\n" + message + "```")
                message = ''
                i = 0

        await ctx.send("```markdown\n" + message + "```")

    @commands.command(name='sub-clear')
    @commands.has_permissions(administrator=True)
    async def sub_clear(self, ctx: commands.context.Context):
        """
        Clear all enabled subscriptions for this channel
        """
        try:
            await self.hunt_manager.clear_subscriptions(ctx.channel.id)
        except KeyError as e:
            self._log.info(e)
            await ctx.reply("No subscriptions have been specified for this channel")
            return

        await ctx.reply("Subscriptions for this channel have been cleared")

class SRankInteraction(discord.ui.View):
    def __init__(self, options=None, placeholder=None): #, custom_id=None):
        super().__init__()
        select = self.children[0]
        select.options = options
        select.placeholder = placeholder
        select.min_values = 1
        select.max_values = 1
        #select.custom_id=custom_id

    @discord.ui.select()
    async def on_select(self, interaction: discord.Interaction, choice): #, custom_id: str, choice):
        try:
            await interaction.response.send_message("Success on_select", ephemeral=True)
            #if custom_id == "button1":
            #    print('test')
            #    await interaction.response.send_message("Success on_select", ephemeral=True)
            #else:
            #    print('test2')
            #    await interaction.response.send_message("Success on_select2", ephemeral=True)
        except Exception as e:
            print(e)

    #@discord.ui.select()
    #async def on_select2(self, interaction: discord.Interaction, choice):
    #    try:
    #        print('test2')
    #        await interaction.response.send_message("Success on_select", ephemeral=True)
    #    except Exception as e:
    #        print(e)
