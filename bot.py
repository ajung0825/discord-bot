import discord
from discord.ext import commands
from datetime import datetime, timedelta
import os
from pymongo import MongoClient

# 1. MongoDB 연결 설정
# Railway의 Variables에 MONGO_URL을 등록하세요.
MONGO_URL = os.getenv("MONGO_URL") 
cluster = MongoClient(MONGO_URL)
db = cluster["discord_bot"] # 데이터베이스 이름
collection = db["point_data"] # 컬렉션(테이블) 이름

# 봇 권한 설정
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 가져오기/생성 함수 (DB 버전)
def get_user_data(guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    # DB에서 해당 서버와 유저 데이터 검색
    user = collection.find_one({"guild_id": guild_id, "user_id": user_id})
    
    if not user:
        # 데이터가 없으면 새로 생성
        user = {
            "guild_id": guild_id,
            "user_id": user_id,
            "points": 0,
            "last_attendance": None
        }
        collection.insert_one(user)
    
    return user

# 데이터 업데이트 함수
def update_user(guild_id, user_id, update_query):
    collection.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        update_query
    )

@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료! (MongoDB 연동됨)")

# 채팅 포인트
last_chat_time = {}

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    now = datetime.now()
    u_id = message.author.id
    
    if u_id not in last_chat_time or now - last_chat_time[u_id] > timedelta(seconds=15):
        get_user_data(message.guild.id, u_id) # 데이터 없으면 생성용
        update_user(message.guild.id, u_id, {"$inc": {"points": 1}}) # 포인트 1 증가
        last_chat_time[u_id] = now

    await bot.process_commands(message)

# 출석 체크
@bot.command()
async def 출석(ctx):
    user = get_user_data(ctx.guild.id, ctx.author.id)
    today = str(datetime.now().date())

    if user["last_attendance"] == today:
        await ctx.send("이미 오늘 출석하셨습니다!")
        return

    update_user(ctx.guild.id, ctx.author.id, {
        "$inc": {"points": 300},
        "$set": {"last_attendance": today}
    })
    await ctx.send(f"✅ {ctx.author.mention} 출석 완료! +300P")

voice_times = {} # 유저의 입장 시간을 기록할 딕셔너리

# 음성 포인트 처리 (1분당 5포인트)
@bot.event
async def on_voice_state_update(member, before, after):
    # 1. 음성 채널 입장 시
    if not before.channel and after.channel:
        # 입장 시간을 기록 (메모리에 임시 저장)
        voice_times[member.id] = datetime.now()

    # 2. 음성 채널 퇴장 시
    elif before.channel and not after.channel:
        if member.id in voice_times:
            join_time = voice_times.pop(member.id)
            # 머문 시간 계산 (분 단위)
            duration = datetime.now() - join_time
            minutes = duration.seconds // 60

            if minutes > 0:
                points_to_add = minutes * 5
                
                # DB 데이터가 있는지 먼저 확인(없으면 생성)
                get_user_data(before.channel.guild.id, member.id)
                
                # DB에 포인트 합산
                update_user(before.channel.guild.id, member.id, {
                    "$inc": {"points": points_to_add}
                })
                
                print(f"DEBUG: {member.display_name} - {minutes}분 체류, {points_to_add}P 지급 완료")

# 타임아웃 명령어 (DB 버전으로 보강)
@bot.command()
async def 타임아웃(ctx, member: discord.Member):
    user = get_user_data(ctx.guild.id, ctx.author.id)
    cost = 900

    if user["points"] < cost:
        await ctx.send(f"포인트가 부족합니다! (필요: {cost}P / 보유: {user['points']}P)")
        return

    if member.guild_permissions.administrator:
        await ctx.send("관리자는 타임아웃시킬 수 없어요.")
        return

    try:
        await member.timeout(timedelta(minutes=1), reason="포인트 사용 타임아웃")
        
        # DB에서 포인트 차감 ($inc에 마이너스 값 사용)
        update_user(ctx.guild.id, ctx.author.id, {"$inc": {"points": -cost}})
        
        await ctx.send(f"💥 {ctx.author.mention}님이 {member.mention}님을 1분간 타임아웃 시켰습니다! (-{cost}P)")
    except Exception as e:
        await ctx.send(f"오류가 발생했습니다: {e}")

# 포인트 확인
@bot.command()
async def 포인트(ctx):
    user = get_user_data(ctx.guild.id, ctx.author.id)
    await ctx.send(f"📍 {ctx.author.display_name}님의 포인트: **{user['points']}P**")

# 랭킹 (서버별)
@bot.command()
async def 랭킹(ctx):
    guild_id = str(ctx.guild.id)
    
    # DB에서 해당 서버 데이터만 포인트 역순으로 5개 가져오기
    top_users = collection.find({"guild_id": guild_id}).sort("points", -1).limit(5)

    embed = discord.Embed(title=f"🏆 {ctx.guild.name} 랭킹", color=discord.Color.gold())
    
    rank_text = ""
    for i, data in enumerate(top_users, start=1):
        try:
            member = ctx.guild.get_member(int(data["user_id"]))
            name = member.display_name if member else f"유저({data['user_id']})"
        except:
            name = "알 수 없음"
        rank_text += f"{i}위. {name} - {data['points']}P\n"

    embed.description = rank_text if rank_text else "데이터가 없습니다."
    await ctx.send(embed=embed)

# 관리자 포인트 지급
@bot.command()
@commands.has_permissions(administrator=True)
async def 지급(ctx, member: discord.Member, amount: int):
    get_user_data(ctx.guild.id, member.id)
    update_user(ctx.guild.id, member.id, {"$inc": {"points": amount}})
    await ctx.send(f"✅ {member.display_name}님에게 {amount}P를 지급했습니다.")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
