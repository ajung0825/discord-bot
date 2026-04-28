import discord
from discord.ext import commands
from datetime import datetime, timedelta
import json
import os

# 봇 권한 설정
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장소
users = {}
voice_times = {}

# 데이터 저장
def save_data():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)

# 데이터 불러오기
def load_data():
    global users
    if os.path.exists("users.json"):
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)

# 봇 실행 시 데이터 로드
@bot.event
async def on_ready():
    load_data()
    print(f"{bot.user} 로그인 완료!")

# 유저 데이터 가져오기
def get_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            "points": 0,
            "last_attendance": None
        }
    return users[user_id]

# 도움말
@bot.command(name="명령어")
async def 도움말(ctx):
    embed = discord.Embed(
        title="📘 봇 도움말",
        description="현재 사용 가능한 명령어 목록입니다.",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="👤 유저 기능",
        value=(
            "`!출석` - 하루 1회 출석 (300P)\n"
            "`!포인트` - 내 포인트 확인\n"
            "`!랭킹` - 랭킹 확인\n"
            "`!타임아웃 @유저` - 900P 사용"
        ),
        inline=False
    )

    embed.add_field(
        name="👑 관리자 기능",
        value=(
            "`!지급 @유저 금액`\n"
            "`!차감 @유저 금액`"
        ),
        inline=False
    )

    await ctx.send(embed=embed)

# 채팅 포인트
last_chat_time = {}

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user = get_user(message.author.id)

    now = datetime.now()
    if message.author.id not in last_chat_time or \
       now - last_chat_time[message.author.id] > timedelta(seconds=15):

        user["points"] += 1
        save_data()
        last_chat_time[message.author.id] = now

    await bot.process_commands(message)

# 음성 포인트 (1분당 5포인트)
@bot.event
async def on_voice_state_update(member, before, after):
    if not before.channel and after.channel:
        voice_times[member.id] = datetime.now()

    elif before.channel and not after.channel:
        if member.id in voice_times:
            join_time = voice_times.pop(member.id)
            minutes = (datetime.now() - join_time).seconds // 60

            if minutes > 0:
                points = minutes * 5
            else:
                points = 0

            user = get_user(member.id)
            user["points"] += points
            save_data()

# 출석
@bot.command()
async def 출석(ctx):
    user = get_user(ctx.author.id)
    today = str(datetime.now().date())

    if user["last_attendance"] == today:
        await ctx.send("이미 출석했어요")
        return

    user["points"] += 300
    user["last_attendance"] = today
    save_data()

    await ctx.send(f"{ctx.author.mention} 출석 완료! +50포인트")

# 타임아웃
@bot.command()
async def 타임아웃(ctx, member: discord.Member):
    user = get_user(ctx.author.id)
    cost = 900

    if user["points"] < cost:
        await ctx.send("포인트가 부족합니다")
        return

    if member.guild_permissions.administrator:
        await ctx.send("관리자는 타임아웃할 수 없습니다")
        return

    try:
        await member.timeout(timedelta(minutes=1))
        user["points"] -= cost
        save_data()

        await ctx.send(f"{member.mention}님 1분 타임아웃!")

    except discord.Forbidden:
        await ctx.send("봇 권한이 부족합니다")
    except Exception as e:
        await ctx.send(f"오류 발생: {e}")

# 포인트 확인
@bot.command()
async def 포인트(ctx):
    user = get_user(ctx.author.id)
    await ctx.send(f"{ctx.author.mention} : {user['points']}P")

# 지급
@bot.command()
async def 지급(ctx, member: discord.Member, amount: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("관리자만 가능합니다")
        return

    user = get_user(member.id)
    user["points"] += amount
    save_data()

    await ctx.send(f"{member.mention}님에게 +{amount} 포인트!")

# 차감
@bot.command()
async def 차감(ctx, member: discord.Member, amount: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("관리자만 가능합니다")
        return

    user = get_user(member.id)
    user["points"] -= amount
    save_data()

    await ctx.send(f"{member.mention}님에게 -{amount} 포인트!")

# 랭킹 (안전 버전)
@bot.command()
async def 랭킹(ctx):
    sorted_users = sorted(users.items(), key=lambda x: x[1]["points"], reverse=True)

    embed = discord.Embed(
        title="🏆 포인트 랭킹",
        color=discord.Color.gold()
    )

    my_rank = None
    my_points = 0
    top_text = ""

    # 내 순위 찾기
    for i, (user_id, data) in enumerate(sorted_users, start=1):
        if int(user_id) == ctx.author.id:
            my_rank = i
            my_points = data["points"]
            break

    # TOP 5
    for i, (user_id, data) in enumerate(sorted_users[:5], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            mention = user.mention
        except:
            mention = "알수없음"

        if int(user_id) == ctx.author.id:
            top_text += f"**{i}. {mention} - {data['points']}P**\n"
        else:
            top_text += f"{i}. {mention} - {data['points']}P\n"

    embed.add_field(name="TOP 5", value=top_text, inline=False)

    # TOP5 밖이면 내 순위 표시
    if my_rank and my_rank > 5:
        embed.add_field(
            name="📍 내 순위",
            value=f"**{my_rank}위 - {ctx.author.mention} ({my_points}P)**",
            inline=False
        )

    await ctx.send(embed=embed)

bot.run(os.getenv("DISCORD_TOKEN"))