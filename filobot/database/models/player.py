from .. import BaseModel
from peewee import IntegerField, CharField, PrimaryKeyField

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
