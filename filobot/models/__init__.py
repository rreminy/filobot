import os
import sys
import logging
import datetime
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
