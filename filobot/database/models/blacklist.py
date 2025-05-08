import datetime
from .. import BaseModel
from peewee import PrimaryKeyField, DateTimeField

class Blacklist(BaseModel):
    guild_id    = PrimaryKeyField()
    ban_date    = DateTimeField(default=datetime.datetime.now)
