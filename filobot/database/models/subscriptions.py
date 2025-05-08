from .. import BaseModel
from peewee import IntegerField, CharField

class Subscriptions(BaseModel):
    channel_id = IntegerField(index=True)
    world = CharField(index=True)
    category = CharField(index=True)
    event = CharField()

class SubscriptionsMeta(BaseModel):
    channel_id = IntegerField(index=True)
    attachName = CharField(index=True, null=True)
    name = CharField()
    value = CharField()
