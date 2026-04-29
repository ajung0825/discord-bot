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

# 데이터 저장소 (서버별 구분 구조)
# { "guild_id": { "user_id": { "points": 0, "last_attendance": "date" } } }
users = {}
voice_times = {}
last_chat_time = {}

# 데이터 저장
def save_data():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# 데이터 불러오기
def load_data():
    global users
    if os.path.exists("users.json"):
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                users = json.load(f)
        except json.JSONDecodeError:
            users = {}

# 유저 데이터 가져오기 (서버 ID와 유저 ID 필요)
def get_user(guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    if guild_id not in users:
        users[guild_id] = {}
    
    if user_id not in users[guild_id]:
        users[guild_id][user_id] = {
            "points": 0,
            "last_attendance": None
        }
    return users[guild_id][user_id]

@bot.event
async def on_ready():
    load_data()
    print(f"{bot.user} 로그인 완료 및 데이터 로드 성공!")

# 기본 역할 지급
@bot.event
async def on_member_join(member):
    # 역할 ID를 해당 서버의 것으로 변경하세요
    role_id = 1498677081029087467 
    role = member.guild.get_role(role_id)
    
    if role:
        try:
            await member.add_roles(role)
            print(f"{member}에게 기본 역할 지급 완료")
        except discord.Forbidden:
            print("역할 지급 권한이 없습니다.")
    else:
        print(f"ID {role_id}에 해당하는 역할을 찾을 수 없음")

# 도움말
@bot.command(name="명령어")
async def 도움말(ctx):
    embed = discord.Embed(
        title="📘 서버별 포인트 시스템 도움말",
        description="이 서버에서 사용 가능한 명령어 목록입니다.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="👤 유저 기능",
        value="`!출석`, `!포인트`, `!랭킹`, `!타임아웃 @유저`",
        inline=False
    )
    embed.add_field(
        name="👑 관리자 기능",
        value="`!지급 @유저 금액`, `!차감 @유저 금액`",
        inline=False
    )
    await ctx.send(embed=embed)

# 채팅 포인트 (서버별)
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    user = get_user(message.guild.id, message.author.id)
    now = datetime.now()
    
    # 15초 쿨타임
    if message.author.id not in last_chat_time or \
       now - last_chat_time[message.author.id] > timedelta(seconds=15):
        user["points"] += 1
        save_data()
        last_chat_time[message.author.id] = now

    await bot.process_commands(message)

# 음성 포인트 (서버별)
@bot.event
async def on_voice_state_update(member, before, after):
    # 입장
    if not before.channel and after.channel:
        voice_times[member.id] = datetime.now()
    # 퇴장
    elif before.channel and not after.channel:
        if member.id in voice_times:
            join_time = voice_times.pop(member.id)
            minutes = (datetime.now() - join_time).seconds // 60

            if minutes > 0:
                user = get_user(before.channel.guild.id, member.id)
                user["points"] += minutes * 5
                save_data()

# 출석
@bot.command()
async def 출석(ctx):
    user = get_user(ctx.guild.id, ctx.author.id)
    today = str(datetime.now().date())

    if user["last_attendance"] == today:
        await ctx.send("이미 오늘 출석체크를 하셨습니다!")
        return

    user["points"] += 300
    user["last_attendance"] = today
    save_data()
    await ctx.send(f"{ctx.author.mention} 출석 완료! +300포인트 (현재: {user['points']}P)")

# 포인트 확인
@bot.command()
async def 포인트(ctx):
    user = get_user(ctx.guild.id, ctx.author.id)
    await ctx.send(f"📍 {ctx.author.display_name}님의 현재 포인트: **{user['points']}P**")

# 타임아웃 (포인트 사용)
@bot.command()
async def 타임아웃(ctx, member: discord.Member):
    user = get_user(ctx.guild.id, ctx.author.id)
    cost = 900

    if user["points"] < cost:
        await ctx.send(f"포인트가 부족합니다. (필요: {cost}P)")
        return

    if member.guild_permissions.administrator:
        await ctx.send("관리자에게는 사용할 수 없습니다.")
        return

    try:
        await member.timeout(timedelta(minutes=1), reason="포인트 사용 타임아웃")
        user["points"] -= cost
        save_data()
        await ctx.send(f"💥 {ctx.author.mention}님이 {member.mention}님을 1분간 격리했습니다!")
    except Exception as e:
        await ctx.send(f"실행 불가: {e}")

# 관리자 포인트 지급/차감
@bot.command()
@commands.has_permissions(administrator=True)
async def 지급(ctx, member: discord.Member, amount: int):
    user = get_user(ctx.guild.id, member.id)
    user["points"] += amount
    save_data()
    await ctx.send(f"✅ {member.mention}님에게 {amount}포인트를 지급했습니다.")

@bot.command()
@commands.has_permissions(administrator=True)
async def 차감(ctx, member: discord.Member, amount: int):
    user = get_user(ctx.guild.id, member.id)
    user["points"] -= amount
    save_data()
    await ctx.send(f"✅ {member.mention}님의 포인트를 {amount}만큼 차감했습니다.")

# 랭킹 (해당 서버 데이터만)
@bot.command()
async def 랭킹(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in users or not users[guild_id]:
        await ctx.send("이 서버에는 아직 랭킹 데이터가 없습니다.")
        return

    # 해당 서버 유저 리스트만 추출하여 정렬
    sorted_users = sorted(users[guild_id].items(), key=lambda x: x[1]["points"], reverse=True)

    embed = discord.Embed(
        title=f"🏆 {ctx.guild.name} 포인트 랭킹",
        color=discord.Color.gold()
    )

    top_text = ""
    my_rank = "순외"
    
    for i, (user_id, data) in enumerate(sorted_users, start=1):
        # 내 순위 기록
        if int(user_id) == ctx.author.id:
            my_rank = f"{i}위"
            
        # TOP 5까지만 텍스트 구성
        if i <= 5:
            try:
                user = await bot.fetch_user(int(user_id))
                name = user.display_name
            except:
                name = "퇴장한 유저"
            
            line = f"{i}위. **{name}** - {data['points']}P"
            if int(user_id) == ctx.author.id:
                line = f"👉 {line}"
            top_text += line + "\n"

    embed.add_field(name="TOP 5", value=top_text or "데이터 없음", inline=False)
    
    # 내 정보 하단 추가
    user_data = get_user(ctx.guild.id, ctx.author.id)
    embed.set_footer(text=f"내 순위: {my_rank} | 내 포인트: {user_data['points']}P")

    await ctx.send(embed=embed)

# 오류 처리 (관리자 권한 부족 등)
@지급.error
@차감.error
async def admin_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
