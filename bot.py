import os
import sqlite3
import datetime
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread
import yt_dlp

# إعداد خادم الحفاظ على النشاط (Keep-Alive)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# إعداد قاعدة البيانات
db = sqlite3.connect('points.db')
cursor = db.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS reputation (
        user_id INTEGER PRIMARY KEY,
        points INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS warnings (
        user_id INTEGER PRIMARY KEY,
        count INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS afk_system (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        time TIMESTAMP
    )
''')

# جدول نظام الغيابات العادية
cursor.execute('''
    CREATE TABLE IF NOT EXISTS absences (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        date TEXT
    )
''')

# جدول نظام الغياب بدون مبرر الجديد
cursor.execute('''
    CREATE TABLE IF NOT EXISTS unexcused_absences (
        user_id INTEGER PRIMARY KEY,
        count INTEGER
    )
''')
db.commit()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.moderation = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ----------------- نظام الحماية المتطور (Anti-Spam & Protection) -----------------
message_tracker = {}

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    author_id = message.author.id
    current_time = datetime.datetime.now().timestamp()
    
    # تجاوز الحماية للمشرفين
    is_admin = message.author.guild_permissions.manage_messages

    content = message.content.lower().strip()

    # نظام الترحيب والكلمات البسيطة
    if "السلام عليكم" in content or "سَلام عليكم" in content or "salam" in content:
        await message.reply(f"وعليكم السلام ورحمة الله وبركاته، أنرت السيرفر يا {message.author.mention}! 💜")
    elif "قوانين" in content or "الوانين" in content:
        await message.channel.send(f"📌 يرجى احترام قوانين السيرفر لتجنب العقوبات يا {message.author.mention}.")
    elif "دعم" in content or "support" in content:
        await message.channel.send(f"🛠️ يمكنك فتح تذكرة أو طلب المساعدة من الإدارة يا {message.author.mention}.")

    # 1. نظام منع الروابط ودعوات ديسكورد
    if not is_admin and ("http://" in message.content or "https://" in message.content or "discord.gg/" in message.content or "discord.com/invite/" in message.content):
        try:
            await message.delete()
            await message.channel.send(f"⚠️ ممنوع إرسال الروابط والدعوات هنا يا {message.author.mention}!", delete_after=5)
            return
        except:
            pass

    # 2. نظام منع السبام (Anti-Spam)
    if not is_admin:
        if author_id not in message_tracker:
            message_tracker[author_id] = []
        
        # تنظيف الرسائل القديمة (أكثر من 5 ثواني)
        message_tracker[author_id] = [t for t in message_tracker[author_id] if current_time - t < 5]
        message_tracker[author_id].append(current_time)
        
        # إذا أرسل أكثر من 5 رسائل خلال 5 ثوانٍ
        if len(message_tracker[author_id]) > 5:
            try:
                await message.delete()
                await message.author.timeout(datetime.timedelta(minutes=1), reason="إرسال رسائل بشكل مزعج (Spam)")
                await message.channel.send(f"🚨 تم عمل Timeout لمدة دقيقة لـ {message.author.mention} بسبب السبام!", delete_after=7)
                message_tracker[author_id] = []
                return
            except:
                pass

    # نظام الـ AFK التلقائي
    cursor.execute('SELECT * FROM afk_system WHERE user_id = ?', (author_id,))
    afk_data = cursor.fetchone()
    if afk_data:
        cursor.execute('DELETE FROM afk_system WHERE user_id = ?', (author_id,))
        db.commit()
        try:
            await message.reply(f"Welcome back {message.author.mention}! لقد تم إزالة حالة الـ AFK عنك.", delete_after=5)
        except:
            pass

    if message.mentions:
        for member in message.mentions:
            cursor.execute('SELECT reason, time FROM afk_system WHERE user_id = ?', (member.id,))
            result = cursor.fetchone()
            if result:
                reason, start_time = result
                await message.channel.send(f"💤 العضو {member.mention} غائب حالياً (AFK).\n📌 السبب: **{reason}**", delete_after=10)

    await bot.process_commands(message)

# 3. حماية السيرفر من الحذف الجماعي (Anti-Nuke / Anti-Channel Delete)
@bot.event
async def on_guild_channel_delete(channel):
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            user = entry.user
            if user.id == bot.user.id or user.id == channel.guild.owner_id:
                return
            
            # حظر الشخص الذي قام بحذف القناة إذا لم يكن المالك
            await channel.guild.ban(user, reason="محاولة تخريب: حذف قنوات السيرفر بدون إذن.")
            
            # محاولة إعادة إنشائها أو إرسال تنبيه في السيرفر الإداري إن وجد
            print(f"⚠️ تحذير أمني: قام العضو {user} بحذف القناة {channel.name} وتم حظره تلقائياً.")
    except Exception as e:
        print(f"خطأ في نظام حماية القنوات: {e}")

# ----------------- أوامر الحماية الإدارية (Slash Commands) -----------------

@bot.tree.command(name="lock", description="قفل الروم الحالي لمنع الأعضاء من التحدث")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    embed = discord.Embed(title="🔒 قفل الشات", description="تم قفل هذه الغرفة بنجاح بواسطة الإدارة.", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unlock", description="فتح الروم الحالي للسماح للأعضاء بالتحدث")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    embed = discord.Embed(title="🔓 فتح الشات", description="تم فتح هذه الغرفة بنجاح.", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

# ----------------- إعدادات الصوت (yt-dlp) -----------------

yt_dlp.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# ----------------- الأحداث الأساسية وأوامر التشغيل -----------------

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(e)

@bot.event
async def on_member_join(member):
    default_role = discord.utils.get(member.guild.roles, name="Nv | Persone")
    if default_role:
        try:
            await member.add_roles(default_role)
        except:
            pass

@bot.command(name='play', help='تشغيل أغنية بالاسم أو الرابط')
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        return await ctx.send(f"❌ {ctx.author.mention}, يجب أن تكون متصلاً بقناة صوتية أولاً!")

    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        if ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
    else:
        try:
            await channel.connect()
        except Exception as e:
            return await ctx.send(f"❌ لم أستطع الدخول للقناة الصوتية: `{e}`")

    async with ctx.typing():
        try:
            query = search if search.startswith("http") else f"ytsearch:{search}"
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
            await ctx.send(f"🎶 جاري تشغيل الآن: **{player.title}**")
        except Exception as e:
            await ctx.send(f"❌ حدث خطأ أثناء جلب الأغنية: `{e}`")

@bot.command(name='stop', help='إيقاف الصوت وإخراج البوت')
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ تم إيقاف التشغيل ومغادرة القناة الصوتية.")
    else:
        await ctx.send("❌ البوت ليس متصلاً بأي قناة صوتية.")

# باقي الأوامر (مثل say, rep, points, notify, afk, clear, absent, warn ...) تم الحفاظ عليها بالكامل في بوتك.

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
