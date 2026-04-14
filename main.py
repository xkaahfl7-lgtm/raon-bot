import os
import re
import json
import time
import discord
from datetime import datetime
from zoneinfo import ZoneInfo
from discord.ext import commands, tasks

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

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
RESTORE_FLAG_FILE = "attendance_restore_once.flag"

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
    "김강혁": 0,
}

DEFAULT_PROMO = {
    "봉식": 1085,
    "우진": 711,
    "이민우": 157,
    "알루": 75,
}

# =========================
# 수동 복구용 현재 근무자
# 한 번만 적용됨
# =========================
MANUAL_RESTORE_WORKERS = {
    "이민우": 4 * 3600,      # 4시간 근무중
    "김강혁": 90 * 60,       # 1시간 30분 근무중
}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# 공통 함수
# =========================
def is_admin(user: discord.abc.User) -> bool:
    return user.id in ADMIN_IDS


def now_ts() -> int:
    return int(time.time())


def now_kst_text() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")


def format_seconds(sec: int) -> str:
    if sec < 0:
        sec = 0
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}시간 {m:02d}분 {s:02d}초"


def load_json(path: str, default):
    if not os.path.exists(path):
        save_json(path, default)
        return default.copy() if isinstance(default, dict) else default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default.copy() if isinstance(default, dict) else default


def save_json(path: str, data):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)


def load_message_id(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def save_message_id(path: str, message_id: int):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(str(message_id))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)


def normalize_name(name: str) -> str:
    """
    직급/장식/이모지/특수문자 제거해서 본이름만 남김
    """
    name = str(name).strip()
    name = name.replace("ㆍ", "ᆞ").replace("·", "ᆞ").replace("•", "ᆞ")

    upper_name = name.upper().replace(" ", "")
    for prefix in ["(AM)", "(IG)", "(DEV)", "(STAFF)", "(GUIDE)", "(GM)", "(DGM)"]:
        if upper_name.startswith(prefix):
            name = name[len(prefix):]
            break

    if "ᆞ" in name:
        name = name.split("ᆞ")[-1]

    # [임시], [대기], ⭐ 같은 장식 제거
    name = re.sub(r"\[[^\]]+\]", "", name)
    name = name.replace("⭐", "").replace("🌟", "").replace("🐣", "")
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
        "김남정": "김남정",
        "남정": "김남정",

        "알루": "알루",
        "alroo": "알루",
        "alru": "알루",

        "김강혁": "김강혁",
        "강혁": "김강혁",
        "kanghyuk": "김강혁",
    }
    return alias_map.get(lower, name)


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
        ("관리자", "AM"),
        ("IG", "IG"),
        ("인게임관리자", "IG"),
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
    if not uid or str(uid).startswith("legacy::"):
        return None
    for guild in bot.guilds:
        member = guild.get_member(int(uid))
        if member:
            return member
    return None


def get_label_from_uid_or_name(uid: str = None, base_name: str = None) -> str:
    if uid:
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
# 출퇴근 데이터 (user_id 기반)
# =========================
def make_attendance_entry(uid: str, base_name: str, total: int = 0, working: bool = False, start: int = 0) -> dict:
    return {
        "user_id": str(uid),
        "base_name": normalize_name(base_name),
        "total": int(total),
        "working": bool(working),
        "start": int(start) if working else 0
    }


def migrate_attendance(raw: dict) -> dict:
    migrated = {}

    if not isinstance(raw, dict):
        raw = {}

    for key, info in raw.items():
        if not isinstance(info, dict):
            continue

        raw_name = str(info.get("display_name", info.get("base_name", key))).strip()
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

        total = int(info.get("total", 0) or 0)
        working = bool(info.get("working", False))
        start = int(info.get("start", 0) or 0)

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


def write_restore_flag():
    temp_path = f"{RESTORE_FLAG_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(now_kst_text())
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, RESTORE_FLAG_FILE)


async def restore_manual_current_workers_once():
    if os.path.exists(RESTORE_FLAG_FILE):
        return

    data = load_attendance()
    now = now_ts()
    restored_names = []

    for base_name, elapsed_seconds in MANUAL_RESTORE_WORKERS.items():
        normalized = normalize_name(base_name)
        uid = resolve_uid_for_base_name(normalized)

        if uid:
            member = find_member_by_uid(uid)
            if member:
                ensure_attendance_user(member, data)
                data[uid]["base_name"] = normalize_name(member.display_name)
                data[uid]["working"] = True
                data[uid]["start"] = now - int(elapsed_seconds)
                if data[uid]["total"] < DEFAULT_ATTENDANCE.get(normalized, 0):
                    data[uid]["total"] = DEFAULT_ATTENDANCE.get(normalized, 0)
                restored_names.append(build_member_label(member))
                continue

        legacy_uid = f"legacy::{normalized}"
        if legacy_uid not in data:
            data[legacy_uid] = make_attendance_entry(
                legacy_uid,
                normalized,
                DEFAULT_ATTENDANCE.get(normalized, 0),
                True,
                now - int(elapsed_seconds)
            )
        else:
            data[legacy_uid]["base_name"] = normalized
            data[legacy_uid]["working"] = True
            data[legacy_uid]["start"] = now - int(elapsed_seconds)
            if data[legacy_uid]["total"] < DEFAULT_ATTENDANCE.get(normalized, 0):
                data[legacy_uid]["total"] = DEFAULT_ATTENDANCE.get(normalized, 0)
        restored_names.append(normalized)

    save_attendance(data)
    write_restore_flag()

    if restored_names:
        await send_log("🛠 현재 근무자 수동 복구 완료 | " + ", ".join(restored_names))


async def send_record_embed(is_clock_in: bool, member: discord.Member, elapsed: int = 0):
    ch = bot.get_channel(RECORD_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        return

    title = "🟢 출근" if is_clock_in else "🔴 퇴근"
    color = 0x2ECC71 if is_clock_in else 0xE74C3C
    now_text = now_kst_text()

    desc = (
        f"## {title}\n\n"
        f"**관리자**\n{build_member_label(member)}\n\n"
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

        current_total = total

        if working and start > 0:
            elapsed = now_ts() - start
            current_workers.append((label, elapsed))
            current_total += elapsed

        ranking.append((label, current_total))

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

    embed = discord.Embed(
        description=(
            "## 📊 관리자 근무확인\n\n"
            f"### 🟢 현재 근무중\n{current_text}\n\n"
            f"### 🏆 근무랭킹\n{ranking_text}"
        ),
        color=0x3498DB
    )
    embed.set_footer(text=f"마지막 갱신: {now_kst_text()}")
    return embed


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

    @discord.ui.button(
        label="출근",
        style=discord.ButtonStyle.success,
        custom_id="raon_clock_in_button"
    )
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

    @discord.ui.button(
        label="퇴근",
        style=discord.ButtonStyle.danger,
        custom_id="raon_clock_out_button"
    )
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
# 홍보 데이터 (user_id 기반)
# =========================
def make_promo_entry(uid: str, base_name: str, count: int = 0) -> dict:
    return {
        "user_id": str(uid),
        "base_name": normalize_name(base_name),
        "count": int(count)
    }


def migrate_promo(raw: dict) -> dict:
    migrated = {}

    if not isinstance(raw, dict):
        raw = {}

    for key, value in raw.items():
        uid = None
        base_name = None
        count = 0

        if isinstance(value, dict):
            uid = value.get("user_id")
            base_name = normalize_name(value.get("base_name", value.get("display_name", key)))
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
    raw = load_json(PROMO_FILE, {})
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


async def refresh_promo_rank_message():
    ch = bot.get_channel(PROMO_RANK_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        await send_promo_log("❌ 홍보-랭킹 채널을 찾지 못했습니다.")
        return

    data = load_promo()

    sorted_items = sorted(
        data.items(),
        key=lambda x: (-int(x[1].get("count", 0)), normalize_name(x[1].get("base_name", "")))
    )

    lines = ["📊 홍보 횟수"]
    for uid, info in sorted_items:
        label = get_label_from_uid_or_name(uid, info.get("base_name", "알수없음"))
        lines.append(f"{label} — {int(info.get('count', 0))}회")

    lines.append("")
    lines.append("🏆 TOP 10")
    for idx, (uid, info) in enumerate(sorted_items[:10], start=1):
        label = get_label_from_uid_or_name(uid, info.get("base_name", "알수없음"))
        lines.append(f"{idx}위 {label} — {int(info.get('count', 0))}회")

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
# 슬래시 관리자 명령어
# =========================
@bot.tree.command(name="강제퇴근", description="유저 강제퇴근 처리")
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

    await interaction.response.send_message(
        f"{build_member_label(user)} 퇴사처리 완료",
        ephemeral=True
    )
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
async def add_promo(interaction: discord.Interaction, user: discord.Member, count: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    if count <= 0:
        return await interaction.response.send_message("1 이상 입력해주세요.", ephemeral=True)

    data = load_promo()
    ensure_promo_user(user, data)
    uid = str(user.id)

    data[uid]["count"] = int(data[uid].get("count", 0)) + count
    data[uid]["base_name"] = normalize_name(user.display_name)
    save_promo(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 홍보 {count}회 추가 완료",
        ephemeral=True
    )
    await send_promo_log(f"🛠 홍보추가 | {build_member_label(user)} (+{count})")
    await refresh_promo_rank_message()


@bot.tree.command(name="홍보차감", description="홍보 횟수 차감")
async def remove_promo(interaction: discord.Interaction, user: discord.Member, count: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    if count <= 0:
        return await interaction.response.send_message("1 이상 입력해주세요.", ephemeral=True)

    data = load_promo()
    ensure_promo_user(user, data)
    uid = str(user.id)

    data[uid]["count"] = max(0, int(data[uid].get("count", 0)) - count)
    data[uid]["base_name"] = normalize_name(user.display_name)
    save_promo(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 홍보 {count}회 차감 완료",
        ephemeral=True
    )
    await send_promo_log(f"🛠 홍보차감 | {build_member_label(user)} (-{count})")
    await refresh_promo_rank_message()


@bot.tree.command(name="홍보설정", description="홍보 횟수 강제 설정")
async def set_promo(interaction: discord.Interaction, user: discord.Member, count: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    if count < 0:
        return await interaction.response.send_message("0 이상 입력해주세요.", ephemeral=True)

    data = load_promo()
    ensure_promo_user(user, data)
    uid = str(user.id)

    data[uid]["count"] = count
    data[uid]["base_name"] = normalize_name(user.display_name)
    save_promo(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 홍보 {count}회 설정 완료",
        ephemeral=True
    )
    await send_promo_log(f"🛠 홍보설정 | {build_member_label(user)} (= {count})")
    await refresh_promo_rank_message()


@bot.tree.command(name="홍보삭제", description="홍보 데이터 삭제")
async def delete_promo(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    uid = str(user.id)
    data = load_promo()

    if uid not in data:
        return await interaction.response.send_message("홍보 데이터가 없습니다.", ephemeral=True)

    del data[uid]
    save_promo(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 홍보 데이터 삭제 완료",
        ephemeral=True
    )
    await send_promo_log(f"🛠 홍보삭제 | {build_member_label(user)}")
    await refresh_promo_rank_message()


@bot.tree.command(name="홍보랭킹갱신", description="홍보 랭킹 강제 갱신")
async def promo_refresh(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    await refresh_promo_rank_message()
    await interaction.response.send_message("홍보 랭킹 갱신 완료", ephemeral=True)


@bot.tree.command(name="통합정보", description="근무/홍보 통합 정보 확인")
async def combined_info(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    uid = str(user.id)
    attendance = load_attendance()
    promo = load_promo()

    work = attendance.get(uid, make_attendance_entry(uid, normalize_name(user.display_name), 0, False, 0))
    promo_info = promo.get(uid, make_promo_entry(uid, normalize_name(user.display_name), 0))

    current_extra = 0
    if work.get("working") and int(work.get("start", 0) or 0) > 0:
        current_extra = now_ts() - int(work["start"])

    total_text = format_seconds(int(work.get("total", 0)) + current_extra)

    msg = (
        f"👤 {build_member_label(user)}\n"
        f"🟢 현재 근무중: {'예' if work.get('working') else '아니오'}\n"
        f"⏱ 누적 근무시간: {total_text}\n"
        f"📢 홍보 횟수: {int(promo_info.get('count', 0))}회"
    )

    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="중복정리", description="기존 이름기반 중복 데이터 강제 정리")
async def dedupe_data(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    att = load_attendance()
    promo = load_promo()

    save_attendance(att)
    save_promo(promo)

    await refresh_status_message()
    await refresh_promo_rank_message()

    await interaction.response.send_message("중복 정리 완료", ephemeral=True)
    await send_log("🛠 중복정리 실행")
    await send_promo_log("🛠 중복정리 실행")


# =========================
# 자동 갱신
# =========================
@tasks.loop(seconds=10)
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
async def on_member_update(before: discord.Member, after: discord.Member):
    try:
        att = load_attendance()
        promo = load_promo()

        uid = str(after.id)
        base_name = normalize_name(after.display_name)

        if uid in att:
            att[uid]["base_name"] = base_name
            save_attendance(att)

        if uid in promo:
            promo[uid]["base_name"] = base_name
            save_promo(promo)
    except Exception as e:
        print(f"on_member_update error: {e}")


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"슬래시 명령어 동기화 완료: {len(synced)}개")
    except Exception as e:
        print(f"슬래시 명령어 동기화 실패: {e}")

    print(f"Logged in as {bot.user} ({bot.user.id})")

    await restore_manual_current_workers_once()
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

    if message.channel.id == PROMO_CHANNEL_ID:
        image_count = 0
        for att in message.attachments:
            filename = (att.filename or "").lower()
            ctype = att.content_type or ""

            if ctype.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                image_count += 1

        if image_count > 0 and isinstance(message.author, discord.Member):
            base_name = normalize_name(message.author.display_name)

            if not is_excluded(base_name):
                data = load_promo()
                ensure_promo_user(message.author, data)
                uid = str(message.author.id)

                data[uid]["count"] = int(data[uid].get("count", 0)) + image_count
                data[uid]["base_name"] = base_name
                save_promo(data)

                await send_promo_log(f"홍보 인증 | {build_member_label(message.author)} (+{image_count})")
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
