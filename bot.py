import os
import sqlite3
import datetime
import discord
from discord import app_commands
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

# إعداد قاعدة البيانات لحفظ نقاط الاحترام والتحذيرات
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

@bot.command(name='say')
async def say(ctx, *, message: str):
    await ctx.message.delete()
    await ctx.send(message)

# أمر إعطاء نقطة احترام
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
    embed.set_thumbnail(url="https://i.imgur.com/2jCgm2F.png")
    
    await ctx.send(embed=embed)

# أمر لعرض نقاط التقدير
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

# أمر الإشعار العام في الخاص
@bot.command(name='notify')
@commands.has_permissions(administrator=True)
async def notify(ctx, *, message: str):
    await ctx.message.delete()
    status_msg = await ctx.send("⏳ جاري إرسال الإشعار مع المنشن لجميع الأعضاء في الخاص...")
    
    success_count = 0
    for member in ctx.guild.members:
        if member.bot:
            continue
        try:
            embed = discord.Embed(
                title="🚨 تنبيه هام - Fanatic Reds",
                description=f"سلام عليكم {member.mention} 👋\n\n{message}",
                color=discord.Color.red()
            )
            embed.set_image(url="https://i.imgur.com/2jCgm2F.png")
            await member.send(embed=embed)
            success_count += 1
        except Exception:
            pass

    await status_msg.edit(content=f"✅ تم إرسال الإشعار بنجاح إلى **{success_count}** عضواً في الخاص.")


# ----------------- نظام التحذيرات مع التنفيذ التلقائي للعقوبة -----------------

class WarnModal(discord.ui.Modal, title="إنشاء تحذير وعقوبة لعضو"):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    reason = discord.ui.TextInput(
        label="السبب (La raison)",
        placeholder="اكتب سبب التحذير هنا...",
        style=discord.TextStyle.short,
        required=True
    )
    
    punishment = discord.ui.TextInput(
        label="العقوبة (Punition)",
        placeholder="اكتب نوع العقوبة (مثال: Timeout)",
        default="Timeout",
        style=discord.TextStyle.short,
        required=True
    )

    duration = discord.ui.TextInput(
        label="مدة العقوبة (Durée)",
        placeholder="مثال: 24h",
        default="24h",
        style=discord.TextStyle.short,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        # 1. تنفيذ العقوبة تلقائياً
        punishment_text = self.punishment.value.lower()
        duration_text = self.duration.value.lower()
        
        if "timeout" in punishment_text or "mute" in punishment_text:
            try:
                hours = 24
                if 'h' in duration_text:
                    hours = int(duration_text.replace('h', '').strip())
                
                delta = datetime.timedelta(hours=hours)
                await self.member.timeout(delta, reason=self.reason.value)
            except Exception:
                pass

        # 2. حساب رقم التحذير من قاعدة البيانات
        cursor.execute('SELECT count FROM warnings WHERE user_id = ?', (self.member.id,))
        result = cursor.fetchone()
        
        if result is None:
            warn_num = 1
            cursor.execute('INSERT INTO warnings (user_id, count) VALUES (?, ?)', (self.member.id, warn_num))
        else:
            warn_num = result[0] + 1
            cursor.execute('UPDATE warnings SET count = ? WHERE user_id = ?', (warn_num, self.member.id))
        
        db.commit()

        # 3. إنشاء لوحة التحذير ونشرها
        embed = discord.Embed(
            title=f"⚠️ avertissement رقم {warn_num:02d}",
            color=discord.Color.dark_embed()
        )
        embed.add_field(name="العضو (Membre)", value=self.member.mention, inline=False)
        embed.add_field(name="السبب (La raison)", value=self.reason.value, inline=False)
        embed.add_field(name="العقوبة (Punition)", value=self.punishment.value, inline=False)
        embed.add_field(name="مدة العقوبة (Durée de punition)", value=self.duration.value, inline=False)
        
        embed.set_footer(text=f"بواسطة المشرف: {interaction.user.name} | تم تنفيذ العقوبة تلقائياً")

        await interaction.followup.send(embed=embed)

@bot.tree.command(name="warn", description="إرسال تحذير وتنفيذ العقوبة تلقائياً لعضو")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_warn(interaction: discord.Interaction, member: discord.Member):
    modal = WarnModal(member=member)
    await interaction.response.send_modal(modal)

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
