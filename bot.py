import discord
from discord.ext import commands
from discord import app_commands  # 슬래시 명령어를 위한 모듈
from datetime import datetime, timedelta
import json
import os

# 봇 설정
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    # 슬래시 명령어 동기화 (봇이 켜질 때 딱 한 번 실행)
    async def setup_hook(self):
        await self.tree.sync()
        print(f"슬래시 명령어 동기화 완료!")

bot = MyBot()

# 데이터 저장소 및 파일 설정
users = {}
voice_times = {}
last_chat_time = {}

def save_data():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def load_data():
    global users
    if os.path.exists("users.json"):
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {"points": 0, "last_attendance": None}
    return users[user_id]

@bot.event
async def on_ready():
    load_data()
    print(f"{bot.user} 로그인 완료 및 데이터 로드 성공!")

# --- 슬래시 명령어 구역 ---

@bot.tree.command(name="명령어", description="봇의 사용 가능한 명령어 목록을 보여줍니다.")
async def 도움말(interaction: discord.Interaction):
    embed = discord.Embed(title="📘 봇 도움말", color=discord.Color.blue())
    embed.add_field(name="👤 유저 기능", value="`/출석`, `/포인트`, `/랭킹`, `/타임아웃`", inline=False)
    embed.add_field(name="👑 관리자 기능", value="`/지급`, `/차감`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="출석", description="하루 한 번 300포인트를 받습니다.")
async def 출석(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    today = str(datetime.now().date())

    if user["last_attendance"] == today:
        await interaction.response.send_message("이미 오늘 출석체크를 하셨습니다!", ephemeral=True)
        return

    user["points"] += 300
    user["last_attendance"] = today
    save_data()
    await interaction.response.send_message(f"{interaction.user.mention}님, 출석 완료! +300P")

@bot.tree.command(name="포인트", description="나의 현재 포인트를 확인합니다.")
async def 포인트(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    await interaction.response.send_message(f"현재 보유 포인트: **{user['points']}P**")

@bot.tree.command(name="타임아웃", description="900포인트를 사용하여 유저를 1분간 대화 금지 시킵니다.")
@app_commands.describe(member="타임아웃 시킬 멤버를 선택하세요")
async def 타임아웃(interaction: discord.Interaction, member: discord.Member):
    user = get_user(interaction.user.id)
    if user["points"] < 900:
        await interaction.response.send_message("포인트가 부족합니다. (필요: 900P)", ephemeral=True)
        return
    
    try:
        await member.timeout(timedelta(minutes=1))
        user["points"] -= 900
        save_data()
        await interaction.response.send_message(f"{member.mention}님을 1분간 타임아웃 시켰습니다!")
    except Exception as e:
        await interaction.response.send_message(f"오류가 발생했습니다: {e}", ephemeral=True)

@bot.tree.command(name="지급", description="[관리자] 특정 유저에게 포인트를 지급합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def 지급(interaction: discord.Interaction, member: discord.Member, amount: int):
    user = get_user(member.id)
    user["points"] += amount
    save_data()
    await interaction.response.send_message(f"{member.mention}님에게 {amount}P를 지급했습니다.")

@bot.tree.command(name="랭킹", description="포인트 순위를 확인합니다.")
async def 랭킹(interaction: discord.Interaction):
    if not users:
        await interaction.response.send_message("데이터가 없습니다.")
        return
    
    sorted_users = sorted(users.items(), key=lambda x: x[1]["points"], reverse=True)
    embed = discord.Embed(title="🏆 포인트 랭킹 TOP 5", color=discord.Color.gold())
    
    ranking_list = ""
    for i, (u_id, data) in enumerate(sorted_users[:5], start=1):
        ranking_list += f"{i}위: <@{u_id}> - {data['points']}P\n"
    
    embed.description = ranking_list
    await interaction.response.send_message(embed=embed)

# --- 이벤트 구역 (채팅/음성 포인트) ---

@bot.event
async def on_message(message):
    if message.author.bot: return
    user = get_user(message.author.id)
    now = datetime.now()
    if message.author.id not in last_chat_time or now - last_chat_time[message.author.id] > timedelta(seconds=15):
        user["points"] += 1
        save_data()
        last_chat_time[message.author.id] = now
    # 슬래시 명령어와 일반 명령어를 섞어 쓸 때 필요 (여기선 생략 가능)
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if not before.channel and after.channel:
        voice_times[member.id] = datetime.now()
    elif before.channel and not after.channel:
        if member.id in voice_times:
            minutes = (datetime.now() - voice_times.pop(member.id)).seconds // 60
            if minutes > 0:
                user = get_user(member.id)
                user["points"] += minutes * 5
                save_data()

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
