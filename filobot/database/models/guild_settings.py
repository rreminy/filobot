from peewee import *
from .. import BaseModel
from discord.ext import commands

class GuildSettings(BaseModel):
    TYPE_ROLE = 'role'

    # key : default, type
    SETTINGS = {
        'verified': (None, TYPE_ROLE),
        'verified_message': ('{mention} Your account has been verified successfully! You may now remove the validation code from your profile.', None)
    }

    guild_id    = IntegerField()
    name        = CharField()
    value       = CharField(max_length=1024)

    @staticmethod
    async def fetch(setting_key: str, ctx: commands.context.Context):
        if setting_key not in GuildSettings.SETTINGS:
            raise KeyError(f"No setting with the key '{setting_key}' exists - please consult the documentation for more information.")

        default, _type = GuildSettings.SETTINGS[setting_key]

        # Return a default value if the setting hasn't been defined
        try:
            setting = GuildSettings.get((GuildSettings.name == setting_key) & (GuildSettings.guild_id == ctx.guild.id))  # type: GuildSettings
        except DoesNotExist:
            return default

        # TYPE CASTING
        if _type == GuildSettings.TYPE_ROLE:
            return ctx.guild.get_role(int(setting.value))

        return setting.value

    @staticmethod
    async def set(setting_key: str, setting_value, ctx: commands.context.Context):
        if setting_key not in GuildSettings.SETTINGS:
            raise KeyError(f"No setting with the key '{setting_key}' exists - please consult the documentation for more information.")

        default, _type = GuildSettings.SETTINGS[setting_key]

        # TYPE CASTING
        if _type == GuildSettings.TYPE_ROLE:
            setting_value = setting_value.id

        GuildSettings.delete().where((GuildSettings.guild_id == ctx.guild.id) & (GuildSettings.name == setting_key)).execute()
        return GuildSettings.create(guild_id=ctx.guild.id, name=setting_key, value=setting_value)

    @staticmethod
    async def all(ctx: commands.context.Context):
        settings = GuildSettings.select().where(GuildSettings.guild_id == ctx.guild.id).execute()
        return list(settings)
