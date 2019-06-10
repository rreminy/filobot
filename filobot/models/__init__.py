import os
import sys
import logging
import datetime

from discord.ext import commands
from peewee import *


logger = logging.getLogger('peewee')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.WARNING)

db_path = os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'filobot.db')
db = SqliteDatabase(db_path, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class Subscriptions(BaseModel):
    channel_id = IntegerField(index=True)
    world = CharField(index=True)
    category = CharField(index=True)
    event = CharField()


class SubscriptionsMeta(BaseModel):
    channel_id = IntegerField(index=True)
    name = CharField()
    value = CharField()


class ScoutingSessions(BaseModel):

    STATUS_STARTED = 0
    STATUS_CANCELLED = -1
    STATUS_COMPLETED = 1

    channel_id = IntegerField(index=True)
    started_by = IntegerField()
    status = IntegerField()
    scouts = CharField(max_length=1200)
    date = DateTimeField(default=datetime.datetime.now)


class ScoutingHunts(BaseModel):
    scouting_session = ForeignKeyField(ScoutingSessions)
    hunt = CharField()
    scouted_by = CharField()
    discord_user = IntegerField(index=True)
    date = DateTimeField(default=datetime.datetime.now)


class Player(BaseModel):

    STATUS_PENDING  = 0
    STATUS_VERIFIED = 1
    STATUS_BANNED   = -1

    lodestone_id    = PrimaryKeyField()
    discord_id      = IntegerField(index=True)
    name            = CharField(max_length=50)
    world           = CharField(max_length=50)
    status          = IntegerField(default=STATUS_PENDING)
    validation_code = CharField(max_length=36)


class GuildSettings(BaseModel):

    TYPE_ROLE = 'role'

    # key : default, type
    SETTINGS = {
        'verified': (None, TYPE_ROLE)
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

        return GuildSettings.create(guild_id=ctx.guild.id, name=setting_key, value=setting_value)

    @staticmethod
    async def all(ctx: commands.context.Context):
        settings = GuildSettings.select().where(GuildSettings.guild_id == ctx.guild.id).execute()
        return list(settings)

