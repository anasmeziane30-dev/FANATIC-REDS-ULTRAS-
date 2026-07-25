import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

# إعداد خادم ويب وهمي ليبقى البوت شغالاً على Render
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# إعدادات الصلاحيات الأساسية للبوت
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح! البوت يعمل الآن باسم: {bot.user.name}")

# الأمر الذي يجعل البوت يكرر ما تكتبه
@bot.command(name="قول", aliases=["say", "كرر"])
async def say_command(ctx, *, message: str):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(message)

# تشغيل خادم الويب أولاً ثم تشغيل البوت باستخدام متغير البيئة السري
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
