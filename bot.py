import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import os

# --- 봇 설정 (슬래시 명령어 동기화 포함) ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 봇이 켜질 때 슬래시 명령어를 디스코드 서버에 등록/업데이트합니다.
        await self.tree.sync()
        print(f"✅ 슬래시 명령어 동기화 완료!")

bot = MyBot()

# --- 데이터 관리 구역 ---
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
    print(f"🤖 {bot.user}으로 로그인했습니다.")

# --- 슬래시 명령어 기능 구역 ---

@bot.tree.command(name="명령어", description="봇의 모든 명령어 목록을 확인합니다.")
async def 도움말(interaction: discord.Interaction):
    embed = discord.Embed(title="📘 포인트 봇 도움말", color=discord.Color.blue())
    embed.add_field(name="👤 유저", value="`/출석`, `/포인트`, `/랭킹`, `/타임아웃`", inline=False)
    embed.add_field(name="👑 관리자", value="`/지급`, `/차감`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="출석", description="매일 한 번씩 300포인트를 획득합니다.")
async def 출석(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    today = str(datetime.now().date())

    if user["last_attendance"] == today:
        await interaction.response.send_message("❌ 이미 오늘 출석체크를 완료하셨습니다!", ephemeral=True)
        return

    user["points"] += 300
    user["last_attendance"] = today
    save_data()
    await interaction.response.send_message(f"✅ {interaction.user.mention}님, 출석 완료! **+300P**가 지급되었습니다.")

@bot.tree.command(name="포인트", description="본인이 보유한 포인트를 확인합니다.")
async def 포인트(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    await interaction.response.send_message(f"💰 {interaction.user.mention}님의 현재 포인트: **{user['points']}P**")

@bot.tree.command(name="타임아웃", description="900포인트를 소모하여 특정 유저를 1분간 대화 금지 시킵니다.")
@app_commands.describe(member="타임아웃을 적용할 대상 유저를 선택하세요.")
async def 타임아웃(interaction: discord.Interaction, member: discord.Member):
    user = get_user(interaction.user.id)
    cost = 900

    if user["points"] < cost:
        await interaction.response.send_message(f"⚠️ 포인트가 부족합니다! (필요: {cost}P)", ephemeral=True)
        return

    if member.guild_permissions.administrator:
        await interaction.response.send_message("❌ 관리자에게는 타임아웃을 사용할 수 없습니다.", ephemeral=True)
        return

    try:
        await member.timeout(timedelta(minutes=1))
        user["points"] -= cost
        save_data()
        await interaction.response.send_message(f"🔇 {interaction.user.mention}님이 {member.mention}님을 1분간 타임아웃 시켰습니다!")
    except Exception as e:
        await interaction.response.send_message(f"🚫 권한이 없거나 오류가 발생했습니다: {e}", ephemeral=True)

@bot.tree.command(name="지급", description="[관리자] 특정 유저에게 포인트를 지급합니다.")
@app_commands.describe(member="포인트를 줄 유저", amount="지급할 포인트 양")
@app_commands.checks.has_permissions(administrator=True)
async def 지급(interaction: discord.Interaction, member: discord.Member, amount: int):
    user = get_user(member.id)
    user["points"] += amount
    save_data()
    await interaction.response.send_message(f"💎 {member.mention}님에게 **{amount}P**를 지급했습니다.")

@bot.tree.command(name="차감", description="[관리자] 특정 유저의 포인트를 회수합니다.")
@app_commands.describe(member="포인트를 뺏을 유저", amount="차감할 포인트 양")
@app_commands.checks.has_permissions(administrator=True)
async def 차감(interaction: discord.Interaction, member: discord.Member, amount: int):
    user = get_user(member.id)
    user["points"] -= amount
    save_data()
    await interaction.response.send_message(f"📉 {member.mention}님의 포인트를 **{amount}P** 차감했습니다.")

@bot.tree.command(name="랭킹", description="서버의 포인트 순위 TOP 5를 확인합니다.")
async def 랭킹(interaction: discord.Interaction):
    if not users:
        await interaction.response.send_message("📊 아직 랭킹 데이터가 없습니다.", ephemeral=True)
        return

    sorted_users = sorted(users.items(), key=lambda x: x[1]["points"], reverse=True)
    embed = discord.Embed(title="🏆 포인트 랭킹 TOP 5", color=discord.Color.gold())

    description = ""
    for i, (user_id, data) in enumerate(sorted_users[:5], start=1):
        description += f"**{i}위** | <@{user_id}> - {data['points']}P\n"

    embed.description = description
    await interaction.response.send_message(embed=embed)

# --- 자동 포인트 적립 (이벤트) ---

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # 채팅 포인트 (15초 쿨타임)
    user = get_user(message.author.id)
    now = datetime.now()
    if message.author.id not in last_chat_time or now - last_chat_time[message.author.id] > timedelta(seconds=15):
        user["points"] += 1
        save_data()
        last_chat_time[message.author.id] = now
    
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    # 음성 입장
    if not before.channel and after.channel:
        voice_times[member.id] = datetime.now()
    # 음성 퇴장
    elif before.channel and not after.channel:
        if member.id in voice_times:
            join_time = voice_times.pop(member.id)
            minutes = (datetime.now() - join_time).seconds // 60
            if minutes > 0:
                user = get_user(member.id)
                user["points"] += minutes * 5
                save_data()

# 봇 실행
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
