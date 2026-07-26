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

active_guess_games = {}

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 1. نظام الـ AFK التلقائي
    cursor.execute('SELECT * FROM afk_system WHERE user_id = ?', (message.author.id,))
    afk_data = cursor.fetchone()
    if afk_data:
        cursor.execute('DELETE FROM afk_system WHERE user_id = ?', (message.author.id,))
        db.commit()
        try:
            await message.reply(f"Welcome back {message.author.mention}! لقد تم إزالة حالة الـ AFK عنك.", delete_after=5)
        except:
            pass

    # 2. فحص إجابة لعبة تخمين اللاعب
    if message.channel.id in active_guess_games:
        game_data = active_guess_games[message.channel.id]
        accepted_answers = game_data["answers"]
        user_text = message.content.lower().strip()
        
        matched = False
        if len(user_text) >= 3:
            for ans in accepted_answers:
                if user_text in ans:
                    matched = True
                    break
        
        if matched:
            winner = message.author
            
            cursor.execute('SELECT points FROM reputation WHERE user_id = ?', (winner.id,))
            result = cursor.fetchone()
            if result is None:
                new_points = 3
                cursor.execute('INSERT INTO reputation (user_id, points) VALUES (?, ?)', (winner.id, new_points))
            else:
                new_points = result[0] + 3
                cursor.execute('UPDATE reputation SET points = ? WHERE user_id = ?', (new_points, winner.id))
            db.commit()

            embed = discord.Embed(
                title="🎉 مبروك الفوز!",
                description=f"الإجابة صحيحة يا {winner.mention}! اللاعب هو **{game_data['display_name']}**.\n🏆 لقد ربحت **3 نقاط تقدير** إضافية!",
                color=discord.Color.green()
            )
            await message.reply(embed=embed)
            del active_guess_games[message.channel.id]

    # 3. الرد عند منشن الشخص الغائب
    if message.mentions:
        for member in message.mentions:
            cursor.execute('SELECT reason, time FROM afk_system WHERE user_id = ?', (member.id,))
            result = cursor.fetchone()
            if result:
                reason, start_time = result
                await message.channel.send(f"💤 العضو {member.mention} غائب حالياً (AFK).\n📌 السبب: **{reason}**", delete_after=10)

    await bot.process_commands(message)


# ----------------- نظام التحذيرات -----------------
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

        # تطبيق التيم أوت
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


# ----------------- تعليمة /accepté المعدلة للرتب -----------------
@bot.tree.command(name="accepté", description="قبول العضو، سحب رول Nv | Persone وإعطائه رول Member Fanatic")
@app_commands.describe(member="العضو المراد قبوله")
@app_commands.checks.has_permissions(manage_roles=True)
async def slash_accepted(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(thinking=True)

    role_remove_name = "Nv | Persone"
    role_add_name = "Member Fanatic"

    removed_status = "❌ لم يتم العثور على رول Nv | Persone"
    added_status = "❌ لم يتم العثور على رول Member Fanatic"

    # البحث عن رول السحب وإزالته
    role_to_remove = discord.utils.get(interaction.guild.roles, name=role_remove_name)
    if role_to_remove and role_to_remove in member.roles:
        try:
            await member.remove_roles(role_to_remove)
            removed_status = f"✅ تم إزالة رول `{role_remove_name}`"
        except Exception as e:
            removed_status = f"⚠️ فشل إزالة الرول: {e}"

    # البحث عن رول الإضافة ومنحه للعضو
    role_to_add = discord.utils.get(interaction.guild.roles, name=role_add_name)
    if role_to_add:
        try:
            await member.add_roles(role_to_add)
            added_status = f"✅ تم منح رول `{role_add_name}`"
        except Exception as e:
            added_status = f"⚠️ فشل منح الرول: {e}"

    embed = discord.Embed(
        title="✨ ═══════════ [  𝑨𝑪𝑪𝑬𝑷𝑻É ] ═══════════ ✨",
        description="╭──────────────────────────────────────────────────────────────╮\n"
                    f"  👤 **العضو المقبول:** {member.mention}\n"
                    f"  🎉 **الحالة:** تم قبول انضمامك .\n\n"
                    
                
                    "╰──────────────────────────────────────────────────────────────╯",
        color=discord.Color.from_rgb(46, 204, 113)
    )
    embed.set_footer(
        text=f"بواسطة الإدارة: {interaction.user.name}",
        icon_url=interaction.user.display_avatar.url
    )
    embed.timestamp = datetime.datetime.now()

    await interaction.followup.send(content=f"مبروك {member.mention}! 🎊", embed=embed)


keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
