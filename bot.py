import discord
from discord.ext import commands
import yt_dlp
import asyncio

# إعدادات البوت والبادئة (Prefix)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')

# ==================== أمر التنبيّه الجماعي في الخاص (!notify) ====================
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


# ==================== أمر الطرد الجماعي (!kickall) ====================
@bot.command(name='kickall')
@commands.has_permissions(administrator=True)
async def kickall(ctx):
    await ctx.send("⚠️ جاري بدء عملية طرد جميع الأعضاء...")
    success = 0
    failed = 0
    
    for member in ctx.guild.members:
        if member.bot or member == ctx.guild.owner or member == ctx.author:
            continue
        try:
            await member.kick(reason="تنظيف شامل للسيرفر بناءً على طلب الإدارة")
            success += 1
        except Exception as e:
            failed += 1
            
    await ctx.send(f"✅ انتهت العملية. تم طرد `{success}` عضواً، وفشل طرد `{failed}` عضواً.")


# ==================== إعدادات نظام الأغاني (!play) ====================
ytdl_format_options = {
    'format': 'bestaudio/best',
    'nostats': True,
    'noplaylist': True,
    'default_search': 'auto',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable="ffmpeg", options="-vn"), data=data)

@bot.command(name='play', help='تشغيل أغنية من اليوتيوب')
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
            return await ctx.send(f"❌ حدث خطأ أثناء التشغيل: `{e}`")

    await ctx.send(f"🎶 جاري تشغيل الآن: **{player.title}**")


# ==================== تشغيل البوت ====================
# ضع التوكن الخاص بك هنا بدلاً من الرمز النصي
bot.run('YOUR_BOT_TOKEN')
