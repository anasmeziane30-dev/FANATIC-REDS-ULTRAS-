import os
import sqlite3
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# إعداد خادم الويب للحفاظ على البوت مستيقظاً 24/7
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# إعداد قاعدة البيانات لحفظ نقاط الأعضاء
db = sqlite3.connect('points.db')
cursor = db.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS reputation (
        user_id INTEGER PRIMARY KEY,
        points INTEGER
    )
''')
db.commit()

# إعدادات البوت والصلاحيات
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
    await ctx.message.delete()
    await ctx.send(message)

# أمر إعطاء نقطة احترام مع صورة الأولتراس كخلفية
@bot.command(name='rep')
async def rep(ctx, member: discord.Member):
    if member == ctx.author:
        await ctx.send("❌ لا يمكنك إعطاء نقطة لنفسك!")
        return
    
    cursor.execute('SELECT points FROM reputation WHERE user_id = ?', (member.id,))
    result = cursor.fetchone()
    
    if result is None:
        new_points = 1
        cursor.execute('INSERT INTO reputation (user_id, points) VALUES (?, ?)', (member.id, new_points))
    else:
        new_points = result[0] + 1
        cursor.execute('UPDATE reputation SET points = ? WHERE user_id = ?', (new_points, member.id))
    
    db.commit()
    
    embed = discord.Embed(
        title="🌟 تفاعل مميز!",
        description=f"قام **{ctx.author.name}** بمنح نقطة تقدير لـ **{member.name}**\nرصيده الحالي: **{new_points}** نقطة.",
        color=discord.Color.red()
    )
    embed.set_image(url="https://i.imgur.com/2jCgm2F.png")
    
    await ctx.send(embed=embed)

# أمر لعرض عدد النقاط
@bot.command(name='points')
async def points(ctx, member: discord.Member = None):
    target = member or ctx.author
    
    cursor.execute('SELECT points FROM reputation WHERE user_id = ?', (target.id,))
    result = cursor.fetchone()
    
    user_points = result[0] if result else 0
    
    embed = discord.Embed(
        title=f"📊 رصيد نقاط التقدير",
        description=f"العضو **{target.name}** لديه **{user_points}** نقطة احترام.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

# أمر إداري لإرسال الإشعار في الخاص مع منشن (Tag) لكل عضو
@bot.command(name='notify')
@commands.has_permissions(administrator=True)
async def notify(ctx, *, message: str):
    await ctx.message.delete()
    
    status_msg = await ctx.send("⏳ جاري إرسال الإشعار مع المنشن لجميع الأعضاء في الخاص...")
    
    success_count = 0
    fail_count = 0
    
    for member in ctx.guild.members:
        if member.bot:
            continue
        try:
            # إنشاء لوحة خاصة لكل عضو تحتوي على المنشن الخاص به ورسالتك
            embed = discord.Embed(
                title="🚨 تنبيه هام - Fanatic Reds",
                description=f"سلام عليكم {member.mention} 👋\n\n{message}",
                color=discord.Color.red()
            )
            embed.set_image(url="https://i.imgur.com/2jCgm2F.png")
            
            await member.send(embed=embed)
            success_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit(content=f"✅ تم إرسال الإشعار بنجاح إلى **{success_count}** عضواً في الخاص مع التاغ.")

@notify.error
async def notify_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ عذراً، هذا الأمر مخصص للإدارة فقط!")

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
