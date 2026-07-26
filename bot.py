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
        
        matched = any(ans in user_text for ans in accepted_answers)
        
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
    embed.set_thumbnail(url="https://i.imgur.com/2jCgm2F.png")
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
async def notify(ctx, *, message: str):
    await ctx.message.delete()
    status_msg = await ctx.send("⏳ جاري إرسال الإشعار لجميع الأعضاء في الخاص...")
    
    success_count = 0
    for member in ctx.guild.members:
        if member.bot:
            continue
        try:
            embed = discord.Embed(
                title="🚨 تنبيه هام - Fanatic Reds",
                description=f"سلام عليكم {member.mention} 👋\n\n{message}",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://i.imgur.com/2jCgm2F.png")
            await member.send(embed=embed)
            success_count += 1
        except Exception:
            pass

    await status_msg.edit(content=f"✅ تم إرسال الإشعار بنجاح إلى **{success_count}** عضواً.")

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


# ----------------- قائمة اللاعبين مع التلميحات والإجابات المرنة -----------------
@bot.tree.command(name="guessplayer", description="ابدأ تحدي لعبة تخمين اللاعب في الشات!")
async def slash_guessplayer(interaction: discord.Interaction):
    players_pool = [
        {"display": "Riyad Mahrez (رياض محرز)", "clues": "🇩🇿 يلعب في المنتخب الجزائري، فاز بدوري أبطال أوروبا مع مانشستر سيتي.", "answers": ["riyad mahrez", "mahrez", "رياض محرز", "محرز"]},
        {"display": "Ibrahim Maza (إبراهيم ماصة)", "clues": "🇩🇿 موهبة جزائرية صاعدة، يلعب في الدوري الألماني وصانع ألعاب بارز.", "answers": ["ibrahim maza", "maza", "إبراهيم ماصة", "ابراهيم ماصة", "ماصة"]},
        {"display": "Youcef Belaili (يوسف بلايلي)", "clues": "🇩🇿 نجم الخضر، معروف بمهاراته الفردية العالية.", "answers": ["youcef belaili", "belaili", "يوسف بلايلي", "بلايلي"]},
        {"display": "Islam Slimani (إسلام سليماني)", "clues": "🇩🇿 الهداف التاريخي للمنتخب الجزائري، برع في الكرات الهوائية.", "answers": ["islam slimani", "slimani", "إسلام سليماني", "سليماني"]},
        {"display": "Baghdad Bounedjah (بغداد بونجاح)", "clues": "🇩🇿 مهاجم قناص، صاحب هدف نهائي أمم إفريقيا 2019 ضد السنغال.", "answers": ["baghdad bounedjah", "bounedjah", "بغداد بونجاح", "بونجاح"]},
        {"display": "Lionel Messi (ليونيل ميسي)", "clues": "🇦🇷 الأسطورة الحائز على 8 كرات ذهبية، بطل العالم 2022.", "answers": ["lionel messi", "messi", "ليونيل ميسي", "ميسي"]},
        {"display": "Cristiano Ronaldo (كريستيانو رونالدو)", "clues": "🇵🇹 الدون، هداف العالم التاريخي وأسطورة ريال مدريد ومانشستر يونايتد.", "answers": ["cristiano ronaldo", "ronaldo", "كريستيانو رونالدو", "رونالدو", "الدون"]},
        {"display": "Kylian Mbappé (كيليان مبابي)", "clues": "🇫🇷 نجم فرنسا السريع، بطل العالم 2018 وهداف ريال مدريد.", "answers": ["kylian mbappe", "mbappe", "كيليان مبابي", "مبابي"]},
        {"display": "Erling Haaland (إيرلينغ هالاند)", "clues": "🇳🇴 ماكينة الأهداف النرويجية، مرعب المدافعين في مانشستر سيتي.", "answers": ["erling haaland", "haaland", "إيرلينغ هالاند", "هالاند"]},
        {"display": "Kevin De Bruyne (كيفين دي بروين)", "clues": "🇧🇪 مهندس وقائد خط وسط مانشستر سيتي، ملك التمريرات الحاسمة.", "answers": ["kevin de bruyne", "de bruyne", "كيفين دي بروين", "دي بروين"]}
    ]
    
    selected = random.choice(players_pool)
    active_guess_games[interaction.channel.id] = {
        "answers": selected["answers"],
        "display_name": selected["display"]
    }

    embed = discord.Embed(
        title="⚽ تحدي تخمين اللاعب الذكي!",
        description=f"من هو اللاعب المقصود بناءً على التلميحات التالية؟\n\n🔍 **التلميحات:** {selected['clues']}\n\n*اكتب اسم اللاعب (مثل: محرز، ميسي...) في الشات مباشرة لتربح 3 نقاط!*",
        color=discord.Color.from_rgb(0, 150, 255)
    )
    embed.set_footer(text=f"بواسطة: {interaction.user.name} | أسرع شخص يجيب يفوز!")
    
    await interaction.response.send_message(embed=embed)


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

        punishment_text = self.punishment.value.lower()
        duration_text = self.duration.value.lower()
        
        if "timeout" in punishment_text or "mute" in punishment_text:
            try:
                hours = 0
                minutes = 0
                if 'h' in duration_text:
                    hours = int(duration_text.replace('h', '').strip())
                if 'm' in duration_text:
                    minutes = int(duration_text.replace('m', '').strip())
                if 'h' not in duration_text and 'm' not in duration_text:
                    hours = int(duration_text.strip())

                delta = datetime.timedelta(hours=hours, minutes=minutes)
                await self.member.timeout(delta, reason=self.reason.value)
            except Exception as e:
                print(f"فشل الـ Timeout: {e}")

        try:
            role_name = f"Avertissement | {warn_num:02d}"
            role_name_alt = f"Avertissement | {warn_num}"

            role = None
            for r in interaction.guild.roles:
                if r.name.lower() in [role_name.lower(), role_name_alt.lower()]:
                    role = r
                    break

            if role:
                await self.member.add_roles(role)
        except Exception as e:
            print(f"فشل إعطاء الرول: {e}")

        kick_status = ""
        if warn_num >= 3:
            try:
                await self.member.kick(reason="تجاوز الحد الأقصى للتحذيرات")
                kick_status = "\n\n🚨 **[إجراء تلقائي]: تم طرد العضو (Kick) لتخطيه 3 تحذيرات!**"
            except Exception as e:
                kick_status = f"\n\n❌ **فشل الطرد:** {e}"

        embed = discord.Embed(
            title=f"Avertissement | {warn_num:02d}",
            color=discord.Color.from_rgb(20, 50, 120)
        )
        
        embed.add_field(name="👤 العضو:", value=f"{self.member.mention}", inline=False)
        embed.add_field(name="⚖️ العقوبة:", value=f"`{self.punishment.value}`", inline=False)
        embed.add_field(name="📌 السبب:", value=f"{self.reason.value}", inline=False)
        embed.add_field(name="⏳ مدة العقوبة:", value=f"`{self.duration.value}`", inline=False)
        
        if kick_status:
            embed.add_field(name="🚨 حالة إضافية:", value=kick_status, inline=False)

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
    
    removed_roles_count = 0
    try:
        roles_to_remove = [r for r in member.roles if "avertissement" in r.name.lower()]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            removed_roles_count = len(roles_to_remove)
    except Exception:
        pass

    embed = discord.Embed(
        title="🧹 إزالة التحذيرات والعقوبات",
        description=f"تم تنظيف سجل العضو {member.mention} بنجاح.\nتم مسح العداد، رفع التيم أوت، وسحب ({removed_roles_count}) رول.",
        color=discord.Color.from_rgb(46, 204, 113)
    )
    embed.set_footer(
        text=f"بواسطة المشرف: {interaction.user.name}",
        icon_url=interaction.user.display_avatar.url
    )
    embed.timestamp = datetime.datetime.now()
    
    await interaction.followup.send(embed=embed)

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
