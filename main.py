import os
import re
import json
import time
from typing import Tuple

import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("TOKEN")

# =========================
# 관리자 ID
# =========================
ADMIN_IDS = {437138732504842250}

# =========================
# 채널 ID
# =========================
BUTTON_CHANNEL_ID = 1481808025030492180   # 출퇴근 | 버튼
RECORD_CHANNEL_ID = 1479035911726563419   # 출퇴근 | 기록
STATUS_CHANNEL_ID = 1479036025820156035   # 관리자 | 근무확인
LOG_CHANNEL_ID = 1479382504204013568      # 봇로그

PROMO_CHANNEL_ID = 1465360797311172730        # 홍보-인증
PROMO_RANK_CHANNEL_ID = 1481209156508586055   # 홍보-랭킹
PROMO_LOG_CHANNEL_ID = 1481661104580067419    # 홍보-로그

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

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic", ".heif"
}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# 공통
# =========================
def is_admin(user: discord.abc.User) -> bool:
    return user.id in ADMIN_IDS


def now_ts() -> int:
    return int(time.time())


def format_seconds(sec: int) -> str:
    sec = max(0, int(sec or 0))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}시간 {m:02d}분"


def load_json(path: str, default):
    if not os.path.exists(path):
        return json.loads(json.dumps(default))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(default))


def save_json(path: str, data):
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
    name = str(name or "").strip()
    if not name:
        return "알수없음"

    name = name.replace("ㆍ", "ᆞ").replace("·", "ᆞ").replace("•", "ᆞ")
    upper_name = name.upper().replace(" ", "")

    for prefix in ["(AM)", "(IG)", "(DEV)", "(STAFF)", "(GUIDE)", "(GM)", "(DGM)"]:
        if upper_name.startswith(prefix):
            name = name[len(prefix):]
            break

    if "ᆞ" in name:
        name = name.split("ᆞ")[-1]

    name = name.replace(" ", "")
    name = re.sub(r"[^가-힣a-zA-Z0-9]", "", name)

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
        "st이민우": "이민우",
        "st민우": "이민우",
        "minwoo": "이민우",
        "leeminwoo": "이민우",

        "볶음": "볶음",
        "bokkeum": "볶음",

        "알루": "알루",
        "alroo": "알루",
        "alru": "알루",
    }
    return alias_map.get(lower, name or "알수없음")


def is_excluded(name: str) -> bool:
    return normalize_name(name) in EXCLUDED_NAMES


def get_role_prefix(member: discord.Member) -> str:
    role_names = [r.name.upper() for r in member.roles]

    priority = [
        ("GM", "GM"),
        ("총괄", "GM"),
        ("DGM", "DGM"),
        ("부총괄", "DGM"),
        ("DEV", "DEV"),
        ("개발자", "DEV"),
        ("AM", "AM"),
        ("IG", "IG"),
        ("ST", "ST"),
        ("STAFF", "ST"),
        ("스태프", "ST"),
        ("GUIDE", "GUIDE🐣"),
        ("뉴비도우미", "GUIDE🐣"),
    ]

    for key, label in priority:
        ku = key.upper()
        for role_name in role_names:
            if ku in role_name:
                return label
    return ""


def build_member_label(member: discord.Member) -> str:
    base = normalize_name(member.display_name)
    prefix = get_role_prefix(member)
    return f"{prefix}ㆍ{base}" if prefix else base


def resolve_uid_for_base_name(base_name: str):
    target = normalize_name(base_name)
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue
            if normalize_name(member.display_name) == target:
                return str(member.id)
    return None


def find_member_by_uid(uid: str):
    try:
        target_id = int(uid)
    except Exception:
        return None

    for guild in bot.guilds:
        member = guild.get_member(target_id)
        if member:
            return member
    return None


def get_label_from_uid_or_name(uid: str = None, base_name: str = None) -> str:
    if uid and not str(uid).startswith("legacy::"):
        member = find_member_by_uid(uid)
        if member:
            return build_member_label(member)
    return normalize_name(base_name or "알수없음")


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
# 출퇴근
# =========================
def make_attendance_entry(uid: str, base_name: str, total: int = 0, working: bool = False, start: int = 0) -> dict:
    return {
        "user_id": str(uid),
        "base_name": normalize_name(base_name),
        "total": int(total),
        "working": bool(working),
        "start": int(start) if working else 0,
    }


def migrate_attendance(raw: dict) -> dict:
    migrated = {}

    if not isinstance(raw, dict):
        raw = {}

    for key, info in raw.items():
        if not isinstance(info, dict):
            continue

        raw_name = str(info.get("display_name") or info.get("base_name") or key).strip()
        base_name = normalize_name(raw_name)

        if not base_name or is_excluded(base_name):
            continue

        uid = info.get("user_id")
        if uid:
            uid = str(uid)
        else:
            uid = resolve_uid_for_base_name(base_name)

        if not uid:
            uid = f"legacy::{base_name}"

        total = int(info.get("total", info.get("total_time", 0)) or 0)
        working = bool(info.get("working", info.get("is_working", False)))
        start = int(info.get("start", info.get("last_clock_in", 0)) or 0)

        if uid not in migrated:
            migrated[uid] = make_attendance_entry(uid, base_name, total, working, start)
        else:
            migrated[uid]["total"] += total
            if working:
                if not migrated[uid]["working"]:
                    migrated[uid]["working"] = True
                    migrated[uid]["start"] = start
                else:
                    existing_start = int(migrated[uid].get("start", 0) or 0)
                    if existing_start == 0:
                        migrated[uid]["start"] = start
                    elif start > 0:
                        migrated[uid]["start"] = min(existing_start, start)

    for base_name, sec in DEFAULT_ATTENDANCE.items():
        uid = resolve_uid_for_base_name(base_name)
        if not uid:
            continue

        if uid not in migrated:
            migrated[uid] = make_attendance_entry(uid, base_name, sec, False, 0)
        else:
            if migrated[uid]["total"] < sec:
                migrated[uid]["total"] = sec

    return migrated


def load_attendance() -> dict:
    raw = load_json(ATTENDANCE_FILE, {})
    return migrate_attendance(raw)


def save_attendance(data: dict):
    save_json(ATTENDANCE_FILE, data)


def ensure_attendance_user(member: discord.Member, data: dict):
    uid = str(member.id)
    base_name = normalize_name(member.display_name)
    if uid not in data:
        data[uid] = make_attendance_entry(uid, base_name, DEFAULT_ATTENDANCE.get(base_name, 0), False, 0)
    else:
        data[uid]["base_name"] = base_name


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

    for uid, info in data.items():
        label = get_label_from_uid_or_name(uid, info.get("base_name", "알수없음"))
        total = int(info.get("total", 0) or 0)
        working = bool(info.get("working", False))
        start = int(info.get("start", 0) or 0)

        if working and start > 0:
            elapsed = now_ts() - start
            current_workers.append((label, elapsed))

        ranking.append((label, total))

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

    @discord.ui.button(label="출근", style=discord.ButtonStyle.success, custom_id="raon_clock_in_button")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("서버 안에서만 사용할 수 있습니다.", ephemeral=True)

        member = interaction.user
        base_name = normalize_name(member.display_name)

        if is_excluded(base_name):
            return await interaction.response.send_message("제외 대상입니다.", ephemeral=True)

        data = load_attendance()
        ensure_attendance_user(member, data)
        uid = str(member.id)

        if data[uid]["working"]:
            return await interaction.response.send_message("이미 출근 상태입니다.", ephemeral=True)

        data[uid]["base_name"] = base_name
        data[uid]["working"] = True
        data[uid]["start"] = now_ts()
        save_attendance(data)

        await interaction.response.send_message("🟢 출근 처리되었습니다.", ephemeral=True)
        await send_record_embed(True, member)
        await send_log(f"🟢 출근 | {build_member_label(member)}")
        await refresh_status_message()

    @discord.ui.button(label="퇴근", style=discord.ButtonStyle.danger, custom_id="raon_clock_out_button")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("서버 안에서만 사용할 수 있습니다.", ephemeral=True)

        member = interaction.user
        data = load_attendance()
        uid = str(member.id)

        if uid not in data:
            return await interaction.response.send_message("출근 데이터가 없습니다.", ephemeral=True)

        if not data[uid]["working"]:
            return await interaction.response.send_message("현재 출근 상태가 아닙니다.", ephemeral=True)

        start = int(data[uid].get("start", 0) or 0)
        if start <= 0:
            data[uid]["working"] = False
            data[uid]["start"] = 0
            save_attendance(data)
            return await interaction.response.send_message("근무 데이터가 꼬여 상태만 해제했습니다.", ephemeral=True)

        elapsed = now_ts() - start
        data[uid]["total"] = int(data[uid].get("total", 0)) + elapsed
        data[uid]["working"] = False
        data[uid]["start"] = 0
        data[uid]["base_name"] = normalize_name(member.display_name)
        save_attendance(data)

        await interaction.response.send_message(
            f"🔴 퇴근 처리되었습니다. 이번 근무시간: {format_seconds(elapsed)}",
            ephemeral=True
        )
        await send_record_embed(False, member, elapsed)
        await send_log(f"🔴 퇴근 | {build_member_label(member)} (+{format_seconds(elapsed)})")
        await refresh_status_message()


# =========================
# 홍보
# =========================
def default_promo_state() -> dict:
    return {
        "__meta__": {
            "counted_messages": {},
            "last_recount_at": 0
        }
    }


def make_promo_entry(uid: str, base_name: str, count: int = 0) -> dict:
    return {
        "user_id": str(uid),
        "base_name": normalize_name(base_name),
        "count": int(count),
    }


def migrate_promo(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raw = {}

    meta = raw.get("__meta__", {})
    if not isinstance(meta, dict):
        meta = {}

    counted_messages = meta.get("counted_messages", {})
    if not isinstance(counted_messages, dict):
        counted_messages = {}

    migrated = {
        "__meta__": {
            "counted_messages": counted_messages,
            "last_recount_at": int(meta.get("last_recount_at", 0) or 0),
        }
    }

    for key, value in raw.items():
        if key == "__meta__":
            continue

        uid = None
        base_name = None
        count = 0

        if isinstance(value, dict):
            uid = value.get("user_id") or key
            base_name = normalize_name(value.get("base_name", key))
            count = int(value.get("count", 0) or 0)
        else:
            base_name = normalize_name(key)
            try:
                count = int(value)
            except Exception:
                count = 0

        if not base_name or is_excluded(base_name):
            continue

        if uid:
            uid = str(uid)
        else:
            uid = resolve_uid_for_base_name(base_name)

        if not uid:
            uid = f"legacy::{base_name}"

        if uid not in migrated:
            migrated[uid] = make_promo_entry(uid, base_name, count)
        else:
            migrated[uid]["count"] += count

    for base_name, count in DEFAULT_PROMO.items():
        uid = resolve_uid_for_base_name(base_name)
        if not uid:
            continue
        if uid not in migrated:
            migrated[uid] = make_promo_entry(uid, base_name, count)
        else:
            if migrated[uid]["count"] < count:
                migrated[uid]["count"] = count

    return migrated


def load_promo() -> dict:
    raw = load_json(PROMO_FILE, default_promo_state())
    return migrate_promo(raw)


def save_promo(data: dict):
    save_json(PROMO_FILE, data)


def ensure_promo_user(member: discord.Member, data: dict):
    uid = str(member.id)
    base_name = normalize_name(member.display_name)
    if uid not in data:
        data[uid] = make_promo_entry(uid, base_name, DEFAULT_PROMO.get(base_name, 0))
    else:
        data[uid]["base_name"] = base_name


def ensure_promo_meta(data: dict):
    if "__meta__" not in data or not isinstance(data["__meta__"], dict):
        data["__meta__"] = {"counted_messages": {}, "last_recount_at": 0}
    if "counted_messages" not in data["__meta__"] or not isinstance(data["__meta__"]["counted_messages"], dict):
        data["__meta__"]["counted_messages"] = {}
    if "last_recount_at" not in data["__meta__"]:
        data["__meta__"]["last_recount_at"] = 0


def iter_promo_users(data: dict):
    for uid, info in data.items():
        if uid == "__meta__":
            continue
        if isinstance(info, dict):
            yield uid, info


def is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = (attachment.content_type or "").lower()
    if content_type.startswith("image/"):
        return True
    lower_name = attachment.filename.lower()
    return any(lower_name.endswith(ext) for ext in IMAGE_EXTENSIONS)


def count_promo_attachments(message: discord.Message) -> int:
    if not message.attachments:
        return 0
    return sum(1 for a in message.attachments if is_image_attachment(a))


def build_promo_rank_content(data: dict) -> str:
    sorted_items = sorted(
        list(iter_promo_users(data)),
        key=lambda x: (-int(x[1].get("count", 0)), normalize_name(x[1].get("base_name", "")))
    )

    lines = ["📊 홍보 횟수", ""]
    if not sorted_items:
        lines.append("데이터 없음")
    else:
        for uid, info in sorted_items:
            label = get_label_from_uid_or_name(uid, info.get("base_name", "알수없음"))
            lines.append(f"{label} — {int(info.get('count', 0))}회")

    lines += ["", "🏆 TOP 10"]
    if not sorted_items:
        lines.append("데이터 없음")
    else:
        for idx, (uid, info) in enumerate(sorted_items[:10], start=1):
            label = get_label_from_uid_or_name(uid, info.get("base_name", "알수없음"))
            lines.append(f"{idx}위 {label} — {int(info.get('count', 0))}회")

    return "\n".join(lines)


async def refresh_promo_rank_message():
    ch = bot.get_channel(PROMO_RANK_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        await send_promo_log("❌ 홍보-랭킹 채널을 찾지 못했습니다.")
        return

    data = load_promo()
    content = build_promo_rank_content(data)
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


async def recount_promo_channel(full_reset: bool = True) -> Tuple[int, int, int]:
    channel = bot.get_channel(PROMO_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        raise RuntimeError("홍보-인증 채널을 찾지 못했습니다.")

    base = default_promo_state() if full_reset else load_promo()
    ensure_promo_meta(base)

    if full_reset:
        for base_name, count in DEFAULT_PROMO.items():
            uid = resolve_uid_for_base_name(base_name)
            if not uid:
                continue
            base[uid] = make_promo_entry(uid, base_name, count)

    scanned_messages = 0
    counted_images = 0
    counted_users = set()
    counted_map = {}

    async for message in channel.history(limit=None, oldest_first=True):
        if message.author.bot:
            continue

        image_count = count_promo_attachments(message)
        if image_count <= 0:
            continue

        scanned_messages += 1
        uid = str(message.author.id)
        base_name = normalize_name(getattr(message.author, "display_name", message.author.name))

        if is_excluded(base_name):
            continue

        if uid not in base:
            base[uid] = make_promo_entry(uid, base_name, 0)

        base[uid]["base_name"] = base_name
        base[uid]["count"] = int(base[uid].get("count", 0)) + image_count
        counted_images += image_count
        counted_users.add(uid)
        counted_map[str(message.id)] = {
            "user_id": uid,
            "count": image_count
        }

    base["__meta__"]["counted_messages"] = counted_map
    base["__meta__"]["last_recount_at"] = now_ts()
    save_promo(base)
    await refresh_promo_rank_message()

    return scanned_messages, counted_images, len(counted_users)


# =========================
# 슬래시 명령어
# =========================
@bot.tree.command(name="강제퇴근", description="유저 강제퇴근 처리")
@app_commands.describe(user="강제퇴근할 유저")
async def force_clock_out(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    data = load_attendance()
    ensure_attendance_user(user, data)
    uid = str(user.id)

    if not data[uid]["working"]:
        return await interaction.response.send_message("현재 근무중이 아닙니다.", ephemeral=True)

    start = int(data[uid].get("start", 0) or 0)
    elapsed = 0

    if start > 0:
        elapsed = now_ts() - start
        data[uid]["total"] = int(data[uid].get("total", 0)) + elapsed

    data[uid]["working"] = False
    data[uid]["start"] = 0
    data[uid]["base_name"] = normalize_name(user.display_name)
    save_attendance(data)

    await interaction.response.send_message(
        f"강제퇴근 완료: {build_member_label(user)} / 추가 반영 {format_seconds(elapsed)}",
        ephemeral=True
    )
    await send_log(f"🛠 강제퇴근 | {build_member_label(user)} (+{format_seconds(elapsed)})")
    await refresh_status_message()


@bot.tree.command(name="근무시간추가", description="근무시간 추가")
@app_commands.describe(user="대상 유저", minutes="추가할 분")
async def add_work_time(interaction: discord.Interaction, user: discord.Member, minutes: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)
    if minutes <= 0:
        return await interaction.response.send_message("1분 이상 입력해주세요.", ephemeral=True)

    data = load_attendance()
    ensure_attendance_user(user, data)
    uid = str(user.id)

    data[uid]["total"] = int(data[uid].get("total", 0)) + (minutes * 60)
    data[uid]["base_name"] = normalize_name(user.display_name)
    save_attendance(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 근무시간 {minutes}분 추가 완료",
        ephemeral=True
    )
    await send_log(f"🛠 근무시간추가 | {build_member_label(user)} (+{minutes}분)")
    await refresh_status_message()


@bot.tree.command(name="근무시간차감", description="근무시간 차감")
@app_commands.describe(user="대상 유저", minutes="차감할 분")
async def remove_work_time(interaction: discord.Interaction, user: discord.Member, minutes: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)
    if minutes <= 0:
        return await interaction.response.send_message("1분 이상 입력해주세요.", ephemeral=True)

    data = load_attendance()
    ensure_attendance_user(user, data)
    uid = str(user.id)

    data[uid]["total"] = max(0, int(data[uid].get("total", 0)) - (minutes * 60))
    data[uid]["base_name"] = normalize_name(user.display_name)
    save_attendance(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 근무시간 {minutes}분 차감 완료",
        ephemeral=True
    )
    await send_log(f"🛠 근무시간차감 | {build_member_label(user)} (-{minutes}분)")
    await refresh_status_message()


@bot.tree.command(name="근무초기화", description="근무시간 0으로 초기화")
@app_commands.describe(user="초기화할 유저")
async def reset_work_time(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    data = load_attendance()
    uid = str(user.id)
    data[uid] = make_attendance_entry(uid, normalize_name(user.display_name), 0, False, 0)
    save_attendance(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 근무 데이터 초기화 완료",
        ephemeral=True
    )
    await send_log(f"🛠 근무초기화 | {build_member_label(user)}")
    await refresh_status_message()


@bot.tree.command(name="퇴사처리", description="출퇴근/홍보 데이터 삭제")
@app_commands.describe(user="퇴사처리할 유저")
async def resign_user(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    uid = str(user.id)
    attendance = load_attendance()
    promo = load_promo()

    removed = False
    if uid in attendance:
        del attendance[uid]
        save_attendance(attendance)
        removed = True

    if uid in promo:
        del promo[uid]
        save_promo(promo)
        removed = True

    if not removed:
        return await interaction.response.send_message("삭제할 데이터가 없습니다.", ephemeral=True)

    await interaction.response.send_message(f"{build_member_label(user)} 퇴사처리 완료", ephemeral=True)
    await send_log(f"🛠 퇴사처리 | {build_member_label(user)}")
    await send_promo_log(f"🛠 퇴사처리 | {build_member_label(user)}")
    await refresh_status_message()
    await refresh_promo_rank_message()


@bot.tree.command(name="현황갱신", description="근무 현황판 강제 갱신")
async def status_refresh(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    await refresh_status_message()
    await interaction.response.send_message("근무 현황 갱신 완료", ephemeral=True)


@bot.tree.command(name="홍보추가", description="홍보 횟수 추가")
@app_commands.describe(user="대상 유저", count="추가할 횟수")
async def add_promo(interaction: discord.Interaction, user: discord.Member, count: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)
    if count <= 0:
        return await interaction.response.send_message("1 이상 입력해주세요.", ephemeral=True)

    data = load_promo()
    ensure_promo_meta(data)
    ensure_promo_user(user, data)
    uid = str(user.id)
    data[uid]["count"] = int(data[uid].get("count", 0)) + count
    save_promo(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 홍보 {count}회 추가 완료",
        ephemeral=True
    )
    await send_promo_log(f"🛠 홍보추가 | {build_member_label(user)} (+{count}회)")
    await refresh_promo_rank_message()


@bot.tree.command(name="홍보차감", description="홍보 횟수 차감")
@app_commands.describe(user="대상 유저", count="차감할 횟수")
async def remove_promo(interaction: discord.Interaction, user: discord.Member, count: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)
    if count <= 0:
        return await interaction.response.send_message("1 이상 입력해주세요.", ephemeral=True)

    data = load_promo()
    ensure_promo_meta(data)
    ensure_promo_user(user, data)
    uid = str(user.id)
    data[uid]["count"] = max(0, int(data[uid].get("count", 0)) - count)
    save_promo(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 홍보 {count}회 차감 완료",
        ephemeral=True
    )
    await send_promo_log(f"🛠 홍보차감 | {build_member_label(user)} (-{count}회)")
    await refresh_promo_rank_message()


@bot.tree.command(name="홍보재집계", description="홍보 인증 채널 전체 기록을 다시 스캔하여 재집계")
async def recount_promo(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        scanned_messages, counted_images, counted_users = await recount_promo_channel(full_reset=True)
        await interaction.followup.send(
            f"홍보 재집계 완료\n"
            f"스캔 메시지: {scanned_messages}개\n"
            f"반영 이미지: {counted_images}개\n"
            f"집계 유저: {counted_users}명",
            ephemeral=True
        )
        await send_promo_log(
            f"🛠 홍보재집계 완료 | 메시지 {scanned_messages}개 / "
            f"이미지 {counted_images}개 / 유저 {counted_users}명"
        )
    except Exception as e:
        await interaction.followup.send(f"홍보 재집계 실패: {e}", ephemeral=True)
        await send_promo_log(f"❌ 홍보재집계 실패 | {e}")


# =========================
# 이벤트
# =========================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id == PROMO_CHANNEL_ID:
        added = count_promo_attachments(message)
        if added > 0:
            data = load_promo()
            ensure_promo_meta(data)

            msg_id = str(message.id)
            if msg_id not in data["__meta__"]["counted_messages"]:
                uid = str(message.author.id)
                base_name = normalize_name(getattr(message.author, "display_name", message.author.name))

                if not is_excluded(base_name):
                    if uid not in data:
                        data[uid] = make_promo_entry(uid, base_name, 0)

                    data[uid]["base_name"] = base_name
                    data[uid]["count"] = int(data[uid].get("count", 0)) + added
                    data["__meta__"]["counted_messages"][msg_id] = {
                        "user_id": uid,
                        "count": added
                    }
                    save_promo(data)
                    await refresh_promo_rank_message()
                    await send_promo_log(
                        f"📸 홍보인증 반영 | {get_label_from_uid_or_name(uid, base_name)} (+{added}회)"
                    )

    await bot.process_commands(message)


@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id != PROMO_CHANNEL_ID:
        return

    data = load_promo()
    ensure_promo_meta(data)
    msg_id = str(message.id)

    info = data["__meta__"]["counted_messages"].get(msg_id)
    if not info:
        return

    uid = str(info.get("user_id"))
    count = int(info.get("count", 0) or 0)

    if uid in data:
        data[uid]["count"] = max(0, int(data[uid].get("count", 0)) - count)

    del data["__meta__"]["counted_messages"][msg_id]
    save_promo(data)
    await refresh_promo_rank_message()
    await send_promo_log(f"🗑 홍보인증 삭제 반영 | {get_label_from_uid_or_name(uid)} (-{count}회)")


@bot.event
async def on_ready():
    print(f"✅ 로그인 완료: {bot.user}")
    bot.add_view(AttendanceView())

    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 동기화 완료: {len(synced)}개")
    except Exception as e:
        print(f"❌ 슬래시 명령어 동기화 실패: {e}")

    await ensure_button_message()
    await refresh_status_message()
    await refresh_promo_rank_message()
    await send_log("🤖 RAON 통합봇 정상 실행")
    await send_promo_log("🤖 RAON 홍보 시스템 정상 실행")


async def ensure_button_message():
    channel = bot.get_channel(BUTTON_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        return

    embed = discord.Embed(
        title="🕒 RAON 출퇴근",
        description="아래 버튼으로 출근 / 퇴근을 진행하세요.",
        color=discord.Color.green()
    )
    view = AttendanceView()

    try:
        async for msg in channel.history(limit=30):
            if msg.author == bot.user:
                try:
                    await msg.edit(embed=embed, view=view)
                    return
                except Exception:
                    pass
    except Exception:
        pass

    await channel.send(embed=embed, view=view)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN 또는 TOKEN 환경변수가 필요합니다.")
    bot.run(TOKEN)
