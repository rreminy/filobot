import logging
import discord
import typing

from discord.ext import commands
from filobot.models import GuildSettings as GuildSettings


class Settings(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot):
        self._log = logging.getLogger(__name__)
        self.bot = bot

    @commands.command(name='set-verified')
    @commands.has_permissions(administrator=True)
    async def set_verified(self, ctx: commands.context.Context, role: discord.Role):
        """
        Change a guild setting
        """
        try:
            await GuildSettings.set('verified', role, ctx)
        except KeyError as e:
            await ctx.send(str(e))
            return

        await ctx.message.add_reaction('✅')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx: commands.context.Context, setting_key: typing.Optional[str] = None):
        """
        List a guild setting or settings
        """
        if setting_key:
            setting_key = setting_key.strip().lower()
            try:
                setting = await GuildSettings.fetch(setting_key, ctx)
            except KeyError as e:
                await ctx.send(str(e))
                return

            await ctx.send(str(setting))
            return

        settings = await GuildSettings.all(ctx)
        output = "```ini\n"
        for setting in settings:  # type: GuildSettings
            output = output + f"{setting.name}: {setting.value}\n"
        output = output + "\n```"

        await ctx.send(output)
