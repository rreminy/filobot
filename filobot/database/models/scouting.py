import datetime
from .. import BaseModel
from peewee import IntegerField, CharField, DateTimeField, ForeignKeyField

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
