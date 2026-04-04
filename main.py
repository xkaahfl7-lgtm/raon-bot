import os
import json
import time
import discord
from discord.ext import commands, tasks

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# =========================
# 채널 ID
# =========================
BUTTON_CHANNEL_ID = 1481808025030492180   # 출퇴근 | 버튼
RECORD_CHANNEL_ID = 1479035911726563419   # 출퇴근 | 기록
STATUS_CHANNEL_ID = 1479036025820156035   # 관리자 | 근무확인
LOG_CHANNEL_ID = 1479382504204013568      # 봇로그

PROMO_CHANNEL_ID = 1465360797311172730    # 홍보-인증
PROMO_RANK_CHANNEL_ID = 1481209156508586055  # 홍보-랭킹
PROMO_LOG_CHANNEL_ID = 1481661104580067419   # 홍보-로그

# =========================
# 파일
# =========================
ATTENDANCE_FILE = "attendance.json"
PROMO_FILE = "promo.json"
STATUS_MSG_FILE = "status_message_id.txt"
PROMO_MSG_FILE = "promo_message_id.txt"

# =========================
# 제외 대상
# =========================
EXCLUDED_NAMES = {"호랭", "혁이"}

# =========================
# 기본값
# =========================
DEFAULT_ATTENDANCE = {
    "볶음": 77 * 3600,
    "우진": 54 * 3600,
    "봉식": 47 * 3600,
    "이민우": 36 * 3600,
}

DEFAULT_PROMO = {
    "봉식": 1085,
    "우진": 711,
    "이민우": 157,
    "알루": 75,
}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# 공통 함수
# =========================
def now_ts() -> int:
    return int(time.time())


def format_seconds(sec: int) -> str:
    if sec < 0:
        sec = 0
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}시간 {m:02d}분"


def load_json(path: str, default: dict) -> dict:
    if not os.path.exists(path):
        save_json(path, default)
        return default.copy()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else default.copy()
    except Exception:
        return default.copy()


def save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_message_id(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def save_message_id(path: str, message_id: int):
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(message_id))


def normalize_name(name: str) -> str:
    """
    직급/장식 제거해서 본이름만 남김
    """
    name = str(name).strip()
    name = name.replace("ㆍ", "ᆞ").replace("·", "ᆞ").replace("•", "ᆞ")
    name = name.replace(" ", "")

    upper_name = name.upper()
    for prefix in ["(AM)", "(IG)", "(DEV)", "(STAFF)", "(GUIDE)", "(GM)", "(DGM)"]:
        if upper_name.startswith(prefix):
            name = name[len(prefix):]
            break

    if "ᆞ" in name:
        name = name.split("ᆞ")[-1]

    if name.endswith("님"):
        name = name[:-1]

    lower = name.lower()
    alias_map = {
        "우진": "우진",
        "ujin": "우진",
        "woojin": "우진",

        "봉식": "봉식",
        "bongsik": "봉식",

        "이민우": "이민우",
        "민우": "이민우",
        "minwoo": "이민우",

        "볶음": "볶음",
        "bokkeum": "볶음",

        "알루": "알루",
        "alroo": "알루",
        "alru": "알루",
        "@𝖆𝖑𝖗𝖔𝖔💥".lower(): "알루",
    }
    return alias_map.get(lower, name)


def is_excluded(name: str) -> bool:
    return normalize_name(name) in EXCLUDED_NAMES


async def send_log(text: str):
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        try:
            await ch.send(text)
        except Exception:
            pass


async def send_promo_log(text: str):
    ch = bot.get_channel(PROMO_LOG_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        try:
            await ch.send(text)
        except Exception:
            pass


# =========================
# 출퇴근 데이터
# =========================
def load_attendance() -> dict:
    raw = load_json(ATTENDANCE_FILE, {})
    return cleanup_attendance(raw)


def save_attendance(data: dict):
    save_json(ATTENDANCE_FILE, data)


def cleanup_attendance(data: dict) -> dict:
    cleaned = {}

    for _, info in data.items():
        raw_name = str(info.get("display_name", "")).strip()
        name = normalize_name(raw_name)

        if not name:
            continue
        if is_excluded(name):
            continue

        total = int(info.get("total", 0) or 0)
        working = bool(info.get("working", False))
        start = int(info.get("start", 0) or 0)

        if name not in cleaned:
            cleaned[name] = {
                "display_name": name,
                "total": total,
                "working": working,
                "start": start if working else 0
            }
        else:
            # total 큰 쪽 유지
            if total > cleaned[name]["total"]:
                cleaned[name]["total"] = total

            # working 상태 유지
            if working:
                if not cleaned[name]["working"]:
                    cleaned[name]["working"] = True
                    cleaned[name]["start"] = start
                else:
                    existing_start = int(cleaned[name]["start"] or 0)
                    if existing_start == 0:
                        cleaned[name]["start"] = start
                    elif start > 0:
                        cleaned[name]["start"] = min(existing_start, start)

    for name, sec in DEFAULT_ATTENDANCE.items():
        if name not in cleaned:
            cleaned[name] = {
                "display_name": name,
                "total": sec,
                "working": False,
                "start": 0
            }
        else:
            if cleaned[name]["total"] < sec:
                cleaned[name]["total"] = sec

    return cleaned


async def send_record_embed(is_clock_in: bool, member: discord.Member, elapsed: int = 0):
    ch = bot.get_channel(RECORD_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        return

    title = "🟢 출근" if is_clock_in else "🔴 퇴근"
    color = 0x2ECC71 if is_clock_in else 0xE74C3C
    now_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    desc = (
        f"## {title}\n\n"
        f"**관리자**\n{member.mention}\n\n"
        f"**시간**\n{now_text}"
    )

    if not is_clock_in:
        desc += f"\n\n**근무시간**\n{format_seconds(elapsed)}"

    embed = discord.Embed(description=desc, color=color)
    await ch.send(embed=embed)


def build_status_embed(data: dict) -> discord.Embed:
    current_workers = []
    ranking = []

    for _, info in data.items():
        name = info.get("display_name", "알수없음")
        total = int(info.get("total", 0) or 0)
        working = bool(info.get("working", False))
        start = int(info.get("start", 0) or 0)

        if working and start > 0:
            elapsed = now_ts() - start
            current_workers.append((name, elapsed))

        ranking.append((name, total))

    current_workers.sort(key=lambda x: x[1], reverse=True)
    ranking.sort(key=lambda x: x[1], reverse=True)

    current_text = "\n".join(
        f"{name} - {format_seconds(elapsed)}"
        for name, elapsed in current_workers
    ) if current_workers else "없음"

    ranking_text = "\n".join(
        f"{idx}위 {name} - {format_seconds(total)}"
        for idx, (name, total) in enumerate(ranking[:10], start=1)
    ) if ranking else "데이터 없음"

    return discord.Embed(
        description=(
            "## 📊 관리자 근무확인\n\n"
            f"### 🟢 현재 근무중\n{current_text}\n\n"
            f"### 🏆 근무랭킹\n{ranking_text}"
        ),
        color=0x3498DB
    )


async def refresh_status_message():
    ch = bot.get_channel(STATUS_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        await send_log("❌ 관리자 | 근무확인 채널을 찾지 못했습니다.")
        return

    data = load_attendance()
    save_attendance(data)

    embed = build_status_embed(data)
    msg_id = load_message_id(STATUS_MSG_FILE)

    if msg_id:
        try:
            msg = await ch.fetch_message(msg_id)
            await msg.edit(embed=embed)
            return
        except Exception:
            pass

    try:
        await ch.purge(limit=20)
    except Exception:
        pass

    msg = await ch.send(embed=embed)
    save_message_id(STATUS_MSG_FILE, msg.id)


class AttendanceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="출근",
        style=discord.ButtonStyle.success,
        custom_id="raon_clock_in_button"
    )
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("서버 안에서만 사용할 수 있습니다.", ephemeral=True)

        member = interaction.user
        name = normalize_name(member.display_name)

        if is_excluded(name):
            return await interaction.response.send_message("제외 대상입니다.", ephemeral=True)

        data = load_attendance()

        if name not in data:
            data[name] = {
                "display_name": name,
                "total": DEFAULT_ATTENDANCE.get(name, 0),
                "working": False,
                "start": 0
            }

        if data[name]["working"]:
            return await interaction.response.send_message("이미 출근 상태입니다.", ephemeral=True)

        data[name]["display_name"] = name
        data[name]["working"] = True
        data[name]["start"] = now_ts()
        save_attendance(data)

        await interaction.response.send_message("🟢 출근 처리되었습니다.", ephemeral=True)
        await send_record_embed(True, member)
        await send_log(f"🟢 출근 | {name}")
        await refresh_status_message()

    @discord.ui.button(
        label="퇴근",
        style=discord.ButtonStyle.danger,
        custom_id="raon_clock_out_button"
    )
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("서버 안에서만 사용할 수 있습니다.", ephemeral=True)

        member = interaction.user
        name = normalize_name(member.display_name)

        data = load_attendance()

        if name not in data:
            return await interaction.response.send_message("출근 데이터가 없습니다.", ephemeral=True)

        if not data[name]["working"]:
            return await interaction.response.send_message("현재 출근 상태가 아닙니다.", ephemeral=True)

        start = int(data[name].get("start", 0) or 0)
        if start <= 0:
            data[name]["working"] = False
            data[name]["start"] = 0
            save_attendance(data)
            return await interaction.response.send_message("근무 데이터가 꼬여 상태만 해제했습니다.", ephemeral=True)

        elapsed = now_ts() - start
        data[name]["total"] = int(data[name].get("total", 0)) + elapsed
        data[name]["working"] = False
        data[name]["start"] = 0
        save_attendance(data)

        await interaction.response.send_message(
            f"🔴 퇴근 처리되었습니다. 이번 근무시간: {format_seconds(elapsed)}",
            ephemeral=True
        )
        await send_record_embed(False, member, elapsed)
        await send_log(f"🔴 퇴근 | {name} (+{format_seconds(elapsed)})")
        await refresh_status_message()


# =========================
# 홍보 데이터
# =========================
def load_promo() -> dict:
    raw = load_json(PROMO_FILE, {})
    return cleanup_promo(raw)


def save_promo(data: dict):
    save_json(PROMO_FILE, data)


def cleanup_promo(data: dict) -> dict:
    cleaned = {}

    for raw_name, count in data.items():
        name = normalize_name(str(raw_name))
        if not name:
            continue
        if is_excluded(name):
            continue

        try:
            count = int(count)
        except Exception:
            count = 0

        if name not in cleaned:
            cleaned[name] = count
        else:
            cleaned[name] = max(cleaned[name], count)

    for name, count in DEFAULT_PROMO.items():
        if name not in cleaned:
            cleaned[name] = count
        else:
            if cleaned[name] < count:
                cleaned[name] = count

    return cleaned


async def refresh_promo_rank_message():
    ch = bot.get_channel(PROMO_RANK_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        await send_promo_log("❌ 홍보-랭킹 채널을 찾지 못했습니다.")
        return

    data = load_promo()
    save_promo(data)

    sorted_items = sorted(data.items(), key=lambda x: (-x[1], x[0]))

    lines = ["📊 홍보 횟수"]
    for name, count in sorted_items:
        lines.append(f"{name} — {count}회")

    lines.append("")
    lines.append("🏆 TOP 10")
    for idx, (name, count) in enumerate(sorted_items[:10], start=1):
        lines.append(f"{idx}위 {name} — {count}회")

    content = "\n".join(lines)
    msg_id = load_message_id(PROMO_MSG_FILE)

    if msg_id:
        try:
            msg = await ch.fetch_message(msg_id)
            await msg.edit(content=content)
            return
        except Exception:
            pass

    try:
        await ch.purge(limit=20)
    except Exception:
        pass

    msg = await ch.send(content)
    save_message_id(PROMO_MSG_FILE, msg.id)


# =========================
# 자동 갱신
# =========================
@tasks.loop(seconds=60)
async def auto_update_status():
    await refresh_status_message()


@auto_update_status.before_loop
async def before_auto_update_status():
    await bot.wait_until_ready()


# =========================
# 시작 시 버튼 재생성
# =========================
async def rebuild_button_message():
    ch = bot.get_channel(BUTTON_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        await send_log("❌ 출퇴근 | 버튼 채널을 찾지 못했습니다.")
        return

    try:
        await ch.purge(limit=20)
    except Exception:
        pass

    embed = discord.Embed(
        description="## 🕒 RAON 관리자 출퇴근\n\n아래 버튼으로 출근 / 퇴근을 진행하세요.",
        color=0x5865F2
    )
    await ch.send(embed=embed, view=AttendanceView())


# =========================
# 이벤트
# =========================
@bot.event
async def setup_hook():
    bot.add_view(AttendanceView())


@bot.event
async def on_ready():
    save_attendance(load_attendance())
    save_promo(load_promo())

    print(f"Logged in as {bot.user} ({bot.user.id})")

    await rebuild_button_message()
    await refresh_status_message()
    await refresh_promo_rank_message()

    if not auto_update_status.is_running():
        auto_update_status.start()

    await send_log("🤖 RAON 통합봇이 정상적으로 실행되었습니다.")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 홍보 인증 채널 처리
    if message.channel.id == PROMO_CHANNEL_ID:
        image_count = 0
        for att in message.attachments:
            filename = (att.filename or "").lower()
            ctype = att.content_type or ""

            if ctype.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                image_count += 1

        if image_count > 0:
            name = normalize_name(message.author.display_name)

            if not is_excluded(name):
                data = load_promo()
                data[name] = int(data.get(name, 0)) + image_count
                save_promo(data)

                await send_promo_log(f"홍보 인증 | {name} (+{image_count})")
                await refresh_promo_rank_message()

    await bot.process_commands(message)


# =========================
# 실행
# =========================
if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_BOT_TOKEN 시크릿이 비어 있습니다.")
    else:
        bot.run(TOKEN)
