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

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

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
db.commit()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(e)

# ----------------- الأحداث التلقائية -----------------

@bot.event
async def on_member_join(member):
    default_role = discord.utils.get(member.guild.roles, name="Nv | Persone")
    if default_role:
        try:
            await member.add_roles(default_role)
        except:
            pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower().strip()

    if "السلام عليكم" in content or "سَلام عليكم" in content or "salam" in content:
        await message.reply(f"وعليكم السلام ورحمة الله وبركاته، أنرت السيرفر يا {message.author.mention}! 💜")
    elif "قوانين" in content or "الوانين" in content:
        await message.channel.send(f"📌 يرجى احترام قوانين السيرفر لتجنب العقوبات يا {message.author.mention}.")
    elif "دعم" in content or "support" in content:
        await message.channel.send(f"🛠️ يمكنك فتح تذكرة أو طلب المساعدة من الإدارة يا {message.author.mention}.")

    if ("http://" in message.content or "https://" in message.content or "discord.gg/" in message.content):
        if not message.author.guild_permissions.manage_messages:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ ممنوع إرسال الروابط هنا يا {message.author.mention}!", delete_after=5)
                return
            except:
                pass

    cursor.execute('SELECT * FROM afk_system WHERE user_id = ?', (message.author.id,))
    afk_data = cursor.fetchone()
    if afk_data:
        cursor.execute('DELETE FROM afk_system WHERE user_id = ?', (message.author.id,))
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

# ----------------- الأوامر العادية -----------------

@bot.command(name='say')
async def say(ctx, *, message: str):
    await ctx.message.delete()
    await ctx.send(message)

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
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='points')
async def points(ctx, member: discord.Member = None):
    target = member or ctx.author
    cursor.execute('SELECT points FROM reputation WHERE user_id = ?', (target.id,))
    result = cursor.fetchone()
    user_points = result[0] if result else 0
    
    embed = discord.Embed(
        title="📊 رصيد نقاط التقدير",
        description=f"العضو **{target.name}** لديه **{user_points}** نقطة احترام.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='notify')
@commands.has_permissions(administrator=True)
async def notify(ctx, *, message: str = ""):
    IMAGE_URL = "https://i.imgur.com/K88ZCJA.jpeg"

    try:
        await ctx.message.delete()
    except:
        pass
    
    embed = discord.Embed(
        title="🚨 تنبيه هام - Fanatic Reds",
        description=message,
        color=discord.Color.from_rgb(235, 47, 6)
    )
    
    if IMAGE_URL:
        embed.set_image(url=IMAGE_URL)
    
    success_count = 0
    fail_count = 0
    
    for member in ctx.guild.members:
        if member.bot:
            continue
        try:
            await member.send(content=f"سلام {member.mention}", embed=embed)
            success_count += 1
        except:
            fail_count += 1
            
    await ctx.send(f"✅ تم إرسال التنبيه في الخاص إلى `{success_count}` عضواً مع الصورة.", delete_after=10)


# ----------------- نظام الأغاني بالبحث عن الاسم (!play) -----------------
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch1', # البحث عن أول نتيجة مطابقة تلقائياً بالاسم
    'source_address': '0.0.0.0',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, search_query, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        
        # إذا لم يكن رابطاً، اجعله يبحث تلقائياً باستخدام ytsearch1
        search = search_query if search_query.startswith("http") else f"ytsearch1:{search_query}"
        
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable="ffmpeg", options="-vn"), data=data)

@bot.command(name='play', help='تشغيل أغنية بالاسم أو الرابط')
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        return await ctx.send("❌ يجب أن تكون متصلاً بقناة صوتية أولاً!")

    channel = ctx.author.voice.channel
    
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
        except Exception as e:
            return await ctx.send(f"❌ حدث خطأ أثناء البحث أو التشغيل: `{e}`")

    await ctx.send(f"🎶 جاري تشغيل الآن: **{player.title}**")


# ----------------- أوامر السلاش -----------------

@bot.tree.command(name="afk", description="تسجيل أنك غائب عن الجهاز (AFK)")
@app_commands.describe(reason="سبب الغياب (اختياري)")
async def slash_afk(interaction: discord.Interaction, reason: str = "غير متواجد حالياً"):
    cursor.execute('INSERT OR REPLACE INTO afk_system (user_id, reason, time) VALUES (?, ?, ?)', 
                   (interaction.user.id, reason, datetime.datetime.now()))
    db.commit()

    embed = discord.Embed(
        title="💤 وضع الغياب (AFK)",
        description=f"تم تفعيل حالة الـ AFK بنجاح لعضونا {interaction.user.mention}.\n📌 السبب: **{reason}**",
        color=discord.Color.orange()
    )
    embed.set_footer(text="سيتم إزالة حالتك تلقائياً بمجرد إرسالك لأي رسالة.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="مسح عدد محدد من الرسائل في الشات")
@app_commands.describe(amount="عدد الرسائل المراد مسحها")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_clear(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ يجب تحديد رقم أكبر من صفر!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"✅ تم مسح `{len(deleted)}` رسالة بنجاح.", ephemeral=True)

class WarnModal(discord.ui.Modal, title="إنشاء تحذير جديد"):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    reason = discord.ui.TextInput(
        label="السبب",
        placeholder="اكتب سبب التحذير هنا...",
        style=discord.TextStyle.short,
        required=True
    )
    
    punishment = discord.ui.TextInput(
        label="العقوبة",
        default="Timeout",
        style=discord.TextStyle.short,
        required=True
    )

    duration = discord.ui.TextInput(
        label="مدة العقوبة",
        default="24h",
        style=discord.TextStyle.short,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        cursor.execute('SELECT count FROM warnings WHERE user_id = ?', (self.member.id,))
        result = cursor.fetchone()
        
        if result is None:
            warn_num = 1
            cursor.execute('INSERT INTO warnings (user_id, count) VALUES (?, ?)', (self.member.id, warn_num))
        else:
            warn_num = result[0] + 1
            cursor.execute('UPDATE warnings SET count = ? WHERE user_id = ?', (warn_num, self.member.id))
        
        db.commit()

        punishment_text = self.punishment.value.lower()
        duration_text = self.duration.value.lower()
        if "timeout" in punishment_text or "mute" in punishment_text:
            try:
                hours = int(duration_text.replace('h', '').strip())
                await self.member.timeout(datetime.timedelta(hours=hours), reason=self.reason.value)
            except:
                pass

        kick_status = ""
        if warn_num >= 3:
            try:
                await self.member.kick(reason="تجاوز الحد الأقص للتحذيرات")
                kick_status = "\n\n🚨 **[إجراء تلقائي]: تم طرد العضو (Kick) لتخطيه 3 تحذيرات!**"
            except Exception as e:
                kick_status = f"\n\n❌ **فشل الطرد:** {e}"

        embed = discord.Embed(
            title=f"⚡ ═══════════ [ ⚠️ Avertissement | {warn_num:02d} ] ═══════════ ⚡",
            description=f"  👤 **العضو المخالف:** {self.member.mention}\n  ⚖️ **العقوبة المطبقة:** `{self.punishment.value}`\n  📌 **سبب التحذير:** `{self.reason.value}`\n  ⏳ **مدة العقوبة:** `{self.duration.value}`{kick_status}",
            color=discord.Color.from_rgb(138, 43, 226)
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="warn", description="إرسال تحذير وتطبيق العقوبة")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_warn(interaction: discord.Interaction, member: discord.Member):
    modal = WarnModal(member=member)
    await interaction.response.send_modal(modal)

@bot.tree.command(name="unwarn", description="إزالة التحذيرات عن عضو")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_unwarn(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(thinking=True)
    cursor.execute('DELETE FROM warnings WHERE user_id = ?', (member.id,))
    db.commit()
    try:
        await member.timeout(None, reason="إزالة التحذيرات")
    except Exception:
        pass
    
    await interaction.followup.send(f"🧹 تم تنظيف سجل التحذيرات لـ {member.mention} بنجاح.", ephemeral=True)

@bot.tree.command(name="accepté", description="قبول العضو ومنحه رول Member Fanatic")
@app_commands.describe(member="العضو المراد قبوله")
@app_commands.checks.has_permissions(manage_roles=True)
async def slash_accepted(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    role_remove_name = "Nv | Persone"
    role_add_name = "Member Fanatic"

    role_to_add = discord.utils.get(interaction.guild.roles, name=role_add_name)
    
    if role_to_add and role_to_add in member.roles:
        await interaction.followup.send(f"العضو {member.mention} مقبول من قبل ✅", ephemeral=True)
        return

    role_to_remove = discord.utils.get(interaction.guild.roles, name=role_remove_name)
    if role_to_remove and role_to_remove in member.roles:
        try:
            await member.remove_roles(role_to_remove)
        except:
            pass

    if role_to_add:
        try:
            await member.add_roles(role_to_add)
        except:
            pass

    await interaction.followup.send(f"تم قبول العضو {member.mention} بنجاح ✅", ephemeral=True)

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
