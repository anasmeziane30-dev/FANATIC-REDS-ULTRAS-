import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# إعداد خادم الويب الوهمي للحفاظ على عمل البوت 24/7
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# إعدادات البوت والصلاحيات (تأكد من تفعيلها من موقع ديسكورد)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

# أمر التكرار (لتجربة استجابة البوت)
@bot.command(name='say')
async def say(ctx, *, message: str):
    await ctx.message.delete() # لحذف رسالتك وإظهار الرسالة نظيفة
    await ctx.send(message)

# تشغيل خادم الويب والبوت بشكل آمن
keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
