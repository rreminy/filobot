from .. import BaseModel
from peewee import IntegerField, CharField

class KillLog(BaseModel):
    hunt_name   = CharField(index=True)
    world       = CharField(max_length=50, index=True)
    found       = IntegerField()
    killed      = IntegerField(null=True)
    kill_time   = IntegerField(null=True)
