import logging
import discord
import typing

from discord.ext import commands
from filobot.models import GuildSettings as GuildSettings, Player


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

    @commands.command(name='set-verified-message')
    @commands.has_permissions(administrator=True)
    async def set_verified_message(self, ctx: commands.context.Context, *, message: str):
        """
        Change the message displayed to users after they have verified their account
        Replacements:
            {mention} :: Replaced with a mention of the verified user
        """
        try:
            await GuildSettings.set('verified_message', message, ctx)
        except KeyError as e:
            await ctx.send(str(e))
            return

        await ctx.message.add_reaction('✅')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx: commands.context.Context, setting_key: typing.Optional[str] = None):
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

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reload(self, ctx: commands.context.Context):
        """
        Reload settings
        Reloading Filo will do the following:
            * Re-apply the verified role to member accounts
        """
        verified_role = await GuildSettings.fetch('verified', ctx)
        status = await ctx.send("Please wait..")

        if verified_role:
            async with ctx.typing():
                await status.edit(content="Synchronizing verified member roles..")
                verified_members = list(Player.select().where(Player.status == Player.STATUS_VERIFIED).execute())
                for member in verified_members:
                    self._log.info(f"Synchronizing member {member.name} ({member.discord_id})")
                    member = ctx.guild.get_member(int(member.discord_id))
                    if member and verified_role not in member.roles:
                        print(f"Adding verified member role to {member.display_name} ({member.id})")
                        await member.add_roles(verified_role)

        await status.delete()
        await ctx.send("Done!", delete_after=5.0)
