import discord
from discord.ext import commands
from datetime import datetime, timedelta
import json
import os

# 봇 권한 설정
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장소
users = {}
voice_times = {}
last_chat_time = {}

# 데이터 저장
def save_data():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# 데이터 불러오기 (구조 검증 로직 추가)
def load_data():
    global users
    if os.path.exists("users.json"):
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                temp_data = json.load(f)
                # 만약 기존 데이터가 서버별 분리가 안 된 옛날 구조라면 비워버립니다 (충돌 방지)
                # 첫 번째 키를 확인해서 그게 서버 ID(길드 ID)인지 확인하는 로직입니다.
                if temp_data and not isinstance(next(iter(temp_data.values())), dict):
                    print("⚠️ 구버전 데이터 포맷 감지: 데이터를 초기화합니다.")
                    users = {}
                else:
                    users = temp_data
        except Exception as e:
            print(f"데이터 로드 중 오류: {e}")
            users = {}

# 서버별 유저 데이터 가져오기 (핵심!)
def get_user(guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    if guild_id not in users:
        users[guild_id] = {} # 서버별 저장 공간 생성
    
    if user_id not in users[guild_id]:
        users[guild_id][user_id] = {
            "points": 0,
            "last_attendance": None
        }
    return users[guild_id][user_id]

@bot.event
async def on_ready():
    load_data()
    print(f"{bot.user} 로그인 완료 (서버별 분리 모드)")

# --- 이벤트 및 명령어 (모두 guild_id 참조 필수) ---

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # 여기서 message.guild.id를 넣어줘야 이 서버만의 데이터가 생성됩니다.
    user = get_user(message.guild.id, message.author.id)
    now = datetime.now()
    
    if message.author.id not in last_chat_time or \
       now - last_chat_time[message.author.id] > timedelta(seconds=15):
        user["points"] += 1
        save_data()
        last_chat_time[message.author.id] = now

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if not before.channel and after.channel:
        voice_times[member.id] = datetime.now()
    elif before.channel and not after.channel:
        if member.id in voice_times:
            join_time = voice_times.pop(member.id)
            minutes = (datetime.now() - join_time).seconds // 60
            if minutes > 0:
                # 퇴장한 채널이 속한 서버의 포인트를 올려줌
                user = get_user(before.channel.guild.id, member.id)
                user["points"] += minutes * 5
                save_data()

@bot.command()
async def 출석(ctx):
    if not ctx.guild: return
    user = get_user(ctx.guild.id, ctx.author.id)
    today = str(datetime.now().date())

    if user["last_attendance"] == today:
        await ctx.send("이미 오늘 출석하셨습니다!")
        return

    user["points"] += 300
    user["last_attendance"] = today
    save_data()
    await ctx.send(f"{ctx.author.mention}님, 이 서버에서 출석 완료! (+300P)")

@bot.command()
async def 포인트(ctx):
    user = get_user(ctx.guild.id, ctx.author.id)
    await ctx.send(f"📍 {ctx.author.display_name}님의 서버 포인트: **{user['points']}P**")

@bot.command()
async def 랭킹(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in users or not users[guild_id]:
        await ctx.send("이 서버에는 아직 데이터가 없습니다.")
        return

    # 현재 서버(guild_id)의 유저들만 필터링해서 정렬
    current_guild_users = users[guild_id]
    sorted_users = sorted(current_guild_users.items(), key=lambda x: x[1]["points"], reverse=True)

    embed = discord.Embed(title=f"🏆 {ctx.guild.name} 랭킹", color=discord.Color.gold())
    
    top_text = ""
    for i, (u_id, data) in enumerate(sorted_users[:5], start=1):
        try:
            member = ctx.guild.get_member(int(u_id))
            name = member.display_name if member else f"유저({u_id})"
        except:
            name = "알 수 없음"
        top_text += f"{i}위. {name} - {data['points']}P\n"

    embed.description = top_text
    await ctx.send(embed=embed)

# 관리자 명령어 (지급/차감)
@bot.command()
@commands.has_permissions(administrator=True)
async def 지급(ctx, member: discord.Member, amount: int):
    user = get_user(ctx.guild.id, member.id)
    user["points"] += amount
    save_data()
    await ctx.send(f"✅ {member.display_name}님에게 {amount}P 지급 완료.")

# (이하 생략 - 타임아웃 등도 동일하게 get_user(ctx.guild.id, ...)를 사용하면 됩니다)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
