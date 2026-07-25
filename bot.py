import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# إعداد خويب الويب الوهمي للحفاظ على عمل البوت
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# إعدادات البوت وصلاحياته
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command(name='say')
async def say(ctx, *, message: str):
    await ctx.message.delete() # لحذف رسالتك وإظهار الرسالة نظيفة
    await ctx.send(message)

# تشغيل البوت
keep_alive()
TOKEN = os.environ.get('MTUzMDUyNjE3NjE4MTg4Mjk4MA.GDm4I-.RHIgdRHej6U0PQhBtsrbz9O7nzMLxKiFjlXg7w')
bot.run(TOKEN)

