import os
import sqlite3
import datetime
import random
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread

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
    # إعطاء رول Nv | Persone تلقائياً عند دخول السيرفر
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

    # 1. نظام الردود التلقائية (Auto-Responder)
    if "السلام عليكم" in content or "سَلام عليكم" in content or "salam" in content:
        await message.reply(f"وعليكم السلام ورحمة الله وبركاته، أنرت السيرفر يا {message.author.mention}! 💜")
    elif "قوانين" in content or "الوانين" in content:
        await message.channel.send(f"📌 يرجى احترام قوانين السيرفر لتجنب العقوبات يا {message.author.mention}.")
    elif "دعم" in content or "support" in content:
        await message.channel.send(f"🛠️ يمكنك فتح تذكرة أو طلب المساعدة من الإدارة يا {message.author.mention}.")

    # 2. نظام حماية الشات من الروابط
    if ("http://" in message.content or "https://" in message.content or "discord.gg/" in message.content):
        if not message.author.guild_permissions.manage_messages:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ ممنوع إرسال الروابط هنا يا {message.author.mention}!", delete_after=5)
                return
            except:
                pass

    # 3. نظام الـ AFK التلقائي
    cursor.execute('SELECT * FROM afk_system WHERE user_id = ?', (message.author.id,))
    afk_data = cursor.fetchone()
    if afk_data:
        cursor.execute('DELETE FROM afk_system WHERE user_id = ?', (message.author.id,))
        db.commit()
        try:
            await message.reply(f"Welcome back {message.author.mention}! لقد تم إزالة حالة الـ AFK عنك.", delete_after=5)
        except:
            pass

    # 4. الرد عند منشن الشخص الغائب
    if message.mentions:
        for member in message.mentions:
            cursor.execute('SELECT reason, time FROM afk_system WHERE user_id = ?', (member.id,))
            result = cursor.fetchone()
            if result:
                reason, start_time = result
                await message.channel.send(f"💤 العضو {member.mention} غائب حالياً (AFK).\n📌 السبب: **{reason}**", delete_after=10)

    await bot.process_commands(message)

# أوامر العادية (Prefix Commands)
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


# ----------------- أشرطة الأوامر السلاش (Slash Commands) -----------------

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


# أمر مسح الرسائل السريع للمشرفين
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


# نظام التحذيرات
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
                await self.member.kick(reason="تجاوز الحد الأقصى للتحذيرات")
                kick_status = "\n\n🚨 **[إجراء تلقائي]: تم طرد العضو (Kick) لتخطيه 3 تحذيرات!**"
            except Exception as e:
                kick_status = f"\n\n❌ **فشل الطرد:** {e}"

        embed = discord.Embed(
            title=f"⚡ ═══════════ [ ⚠️ Avertissement | {warn_num:02d} ] ═══════════ ⚡",
            description="╭──────────────────────────────────────────────────────────────╮\n"
                        f"  👤 **العضو المخالف:** {self.member.mention}\n"
                        f"  ⚖️ **العقوبة المطبقة:** `{self.punishment.value}`\n"
                        f"  📌 **سبب التحذير:** `{self.reason.value}`\n"
                        f"  ⏳ **مدة العقوبة:** `{self.duration.value}`\n"
                        "╰──────────────────────────────────────────────────────────────╯"
                        f"{kick_status}",
            color=discord.Color.from_rgb(138, 43, 226)
        )
        embed.set_footer(
            text=f"بواسطة المشرف: {interaction.user.name}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.timestamp = datetime.datetime.now()

        await interaction.followup.send(embed=embed)

@bot.tree.command(name="warn", description="إرسال تحذير وتطبيق العقوبة وإعطاء الرول لعضو")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_warn(interaction: discord.Interaction, member: discord.Member):
    modal = WarnModal(member=member)
    await interaction.response.send_modal(modal)


@bot.tree.command(name="unwarn", description="إزالة التحذيرات عن عضو ورفع العقوبات")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_unwarn(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(thinking=True)
    cursor.execute('DELETE FROM warnings WHERE user_id = ?', (member.id,))
    db.commit()
    try:
        await member.timeout(None, reason="إزالة التحذيرات")
    except Exception:
        pass
    
    embed = discord.Embed(
        title="🧹 ══════════ [ إزالة التحذيرات والعقوبات ] ══════════ 🧹",
        description=f"  👤 **العضو المستهدف:** {member.mention}\n  ✨ **الحالة:** تم تنظيف السجل ورفع التيم أوت بنجاح.",
        color=discord.Color.from_rgb(138, 43, 226)
    )
    embed.set_footer(text=f"بواسطة المشرف: {interaction.user.name}")
    await interaction.followup.send(embed=embed)


# أمر /accepté مع التحقق من وجود رول Member Fanatic ورسالة سرية (Ephemeral)
@bot.tree.command(name="accepté", description="قبول العضو، سحب رول Nv | Persone وإعطائه رول Member Fanatic")
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

    removed_status = "❌ لم يتم العثور على رول Nv | Persone"
    added_status = "❌ لم يتم العثور على رول Member Fanatic"

    role_to_remove = discord.utils.get(interaction.guild.roles, name=role_remove_name)
    if role_to_remove and role_to_remove in member.roles:
        try:
            await member.remove_roles(role_to_remove)
            removed_status = f"تم إزالة رول {role_remove_name}"
        except Exception as e:
            removed_status = f"فشل إزالة الرول: {e}"

    if role_to_add:
        try:
            await member.add_roles(role_to_add)
            added_status = f"تم منح رول {role_add_name}"
        except Exception as e:
            added_status = f"فشل منح الرول: {e}"

    result_message = f"تم قبول العضو {member.mention} بنجاح ✅\n- {removed_status}\n- {added_status}"
    await interaction.followup.send(result_message, ephemeral=True)


keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
