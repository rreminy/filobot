from filobot import config, bot
from filobot.tasks import update_game, update_hunts, start_server

bot.loop.create_task(update_hunts())
bot.loop.create_task(update_game())
bot.loop.create_task(start_server())

bot.run('NTc5ODE2NDk3ODYyNjcyMzk1.XOKv8w.hODu-k0AewPC-M0PCz33J_wh4CQ')
bot.run(config.get('Bot', 'Token'))
