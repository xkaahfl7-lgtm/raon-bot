import os
import re
import json
import time
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Tuple

import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("TOKEN")
KST = ZoneInfo("Asia/Seoul")

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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ATTENDANCE_FILE = os.path.join(BASE_DIR, "attendance.json")
PROMO_FILE = os.path.join(BASE_DIR, "promo.json")
STATUS_MSG_FILE = os.path.join(BASE_DIR, "status_message_id.txt")
PROMO_MSG_FILE = os.path.join(BASE_DIR, "promo_message_id.txt")

# =========================
# 제외 대상
# =========================
EXCLUDED_NAMES = {"호랭", "혁이"}

# =========================
# 최초 파일 생성용 현재 기준 데이터
# 파일이 없을 때만 사용됨
# 기존 파일이 있으면 절대 덮어쓰지 않음
# =========================
INITIAL_ATTENDANCE = {
    "legacy::봉식": {
        "user_id": "legacy::봉식",
        "base_name": "봉식",
        "total": 47 * 3600,
        "working": True,
        "start": int(time.time()) - ((15 * 3600) + (7 * 60)),
    },
    "legacy::우진": {
        "user_id": "legacy::우진",
        "base_name": "우진",
        "total": 54 * 3600,
        "working": False,
        "start": 0,
    },
    "legacy::혁준": {
        "user_id": "legacy::혁준",
        "base_name": "혁준",
        "total": (4 * 3600) + (44 * 60),
        "working": False,
        "start": 0,
    },
    "legacy::김강혁": {
        "user_id": "legacy::김강혁",
        "base_name": "김강혁",
        "total": 0,
        "working": True,
        "start": int(time.time()) - ((14 * 3600) + (45 * 60)),
    }
}

INITIAL_PROMO = {
    "__meta__": {
        "counted_messages": {},
        "last_recount_at": 0
    },
    "legacy::봉식": {
        "user_id": "legacy::봉식",
        "base_name": "봉식",
        "count": 3322
    },
    "legacy::우진": {
        "user_id": "legacy::우진",
        "base_name": "우진",
        "count": 2271
    },
    "legacy::김강혁": {
        "user_id": "legacy::김강혁",
        "base_name": "김강혁",
        "count": 92
    },
    "legacy::윤": {
        "user_id": "legacy::윤",
        "base_name": "윤",
        "count": 74
    },
    "legacy::혁준": {
        "user_id": "legacy::혁준",
        "base_name": "혁준",
        "count": 69
    },
    "legacy::김남경": {
        "user_id": "legacy::김남경",
        "base_name": "김남경",
        "count": 15
    },
    "legacy::STAFF도겸": {
        "user_id": "legacy::STAFF도겸",
        "base_name": "도겸",
        "count": 9
    },
    "legacy::73야채경찰청치안감": {
        "user_id": "legacy::73야채경찰청치안감",
        "base_name": "73야채경찰청치안감",
        "count": 3
    }
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
def now_ts() -> int:
    return int(time.time())


def format_kst(ts: int | None = None) -> str:
    if ts is None:
        dt = datetime.now(KST)
    else:
        dt = datetime.fromtimestamp(int(ts), tz=KST)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_seconds(sec: int) -> str:
    sec = max(0, int(sec or 0))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}시간 {m:02d}분"


def is_admin(user: discord.abc.User) -> bool:
    return user.id in ADMIN_IDS


def atomic_save_json(path: str, data: Any):
    temp_path = f"{path}.tmp"
    bak_path = f"{path}.bak"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if os.path.exists(path):
        try:
            shutil.copy2(path, bak_path)
        except Exception:
            pass

    os.replace(temp_path, path)


def load_json(path: str, default: Any):
    if not os.path.exists(path):
        atomic_save_json(path, default)
        return json.loads(json.dumps(default))

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        bak_path = f"{path}.bak"
        if os.path.exists(bak_path):
            try:
                with open(bak_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                atomic_save_json(path, data)
                return data
            except Exception:
                pass

        atomic_save_json(path, default)
        return json.loads(json.dumps(default))


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

    original = name
    name = name.replace("ㆍ", " ").replace("·", " ").replace("•", " ")
    name = re.sub(r"[^\w가-힣 ]", " ", name, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()

    tokens = name.split()
    if not tokens:
        return "알수없음"

    blocked_prefixes = {
        "AM", "IG", "DEV", "STAFF", "ST", "GUIDE", "GM", "DGM",
        "뉴비도우미", "스태프", "관리자", "리더"
    }

    filtered = []
    for token in tokens:
        t = token.upper().replace("⭐", "")
        if t in blocked_prefixes:
            continue
        filtered.append(token)

    cleaned = filtered[-1] if filtered else tokens[-1]
    cleaned = cleaned.replace(" ", "")
    cleaned = re.sub(r"[^가-힣a-zA-Z0-9]", "", cleaned)

    alias_map = {
        "ujin": "우진",
        "woojin": "우진",
        "ori": "오리",
        "dokyeom": "도겸",
        "bongsik": "봉식",
        "minwoo": "이민우",
        "leeminwoo": "이민우",
        "bokkeum": "볶음",
        "alru": "알루",
        "alroo": "알루",
        "hyukjun": "혁준",
    }

    lower = cleaned.lower()
    if lower in alias_map:
        return alias_map[lower]

    if cleaned:
        return cleaned

    raw = original.replace(" ", "")
    raw = re.sub(r"[^가-힣a-zA-Z0-9]", "", raw)
    return raw or "알수없음"


def canonical_name(name: str) -> str:
    return normalize_name(name)


def soft_normalize_name(name: str) -> str:
    name = str(name or "").strip()
    if not name:
        return ""
    name = name.replace("ㆍ", " ").replace("·", " ").replace("•", " ")
    name = re.sub(r"[^\w가-힣 ]", " ", name, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()
    return name.replace(" ", "").lower()


def names_match(a: str, b: str) -> bool:
    a_candidates = {
        canonical_name(a),
        soft_normalize_name(a),
        str(a).replace(" ", "").lower()
    }
    b_candidates = {
        canonical_name(b),
        soft_normalize_name(b),
        str(b).replace(" ", "").lower()
    }

    a_candidates = {x for x in a_candidates if x}
    b_candidates = {x for x in b_candidates if x}

    if a_candidates & b_candidates:
        return True

    for x in a_candidates:
        for y in b_candidates:
            if x and y and (x in y or y in x):
                return True
    return False


def is_excluded(name: str) -> bool:
    return canonical_name(name) in EXCLUDED_NAMES


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
    base = canonical_name(member.display_name)
    prefix = get_role_prefix(member)
    return f"{prefix}ㆍ{base}" if prefix else base


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


def find_member_by_base_name(base_name: str):
    target = canonical_name(base_name)
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue
            if canonical_name(member.display_name) == target:
                return member
    return None


def get_label_from_uid_or_name(uid: str = None, base_name: str = None) -> str:
    if uid and not str(uid).startswith("legacy::"):
        member = find_member_by_uid(uid)
        if member:
            return build_member_label(member)

    if base_name:
        member = find_member_by_base_name(base_name)
        if member:
            return build_member_label(member)

    return canonical_name(base_name or "알수없음")


async def send_log(text: str):
    print(f"[{format_kst()}] {text}")
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        try:
            await ch.send(f"[{format_kst()}] {text}")
        except Exception:
            pass


async def send_promo_log(text: str):
    print(f"[{format_kst()}] {text}")
    ch = bot.get_channel(PROMO_LOG_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        try:
            await ch.send(f"[{format_kst()}] {text}")
        except Exception:
            pass


# =========================
# 출퇴근
# =========================
def make_attendance_entry(uid: str, base_name: str, total: int = 0, working: bool = False, start: int = 0) -> dict:
    return {
        "user_id": str(uid),
        "base_name": canonical_name(base_name),
        "total": int(total),
        "working": bool(working),
        "start": int(start) if working else 0,
    }


def migrate_attendance(raw: Dict[str, Any]) -> Dict[str, Any]:
    migrated = {}

    if not isinstance(raw, dict):
        raw = {}

    for key, info in raw.items():
        if not isinstance(info, dict):
            continue

        raw_name = str(info.get("display_name") or info.get("base_name") or key).strip()
        base_name = canonical_name(raw_name)
        if not base_name or is_excluded(base_name):
            continue

        uid = str(info.get("user_id") or key)
        total = int(info.get("total", info.get("total_time", 0)) or 0)
        working = bool(info.get("working", info.get("is_working", False)))
        start = int(info.get("start", info.get("last_clock_in", 0)) or 0)

        if uid not in migrated:
            migrated[uid] = make_attendance_entry(uid, base_name, total, working, start)
        else:
            migrated[uid]["total"] += total
            if working:
                migrated[uid]["working"] = True
                old_start = int(migrated[uid].get("start", 0) or 0)
                if old_start == 0 or (start > 0 and start < old_start):
                    migrated[uid]["start"] = start

    return migrated


def merge_same_person_attendance(data: Dict[str, Any]) -> Dict[str, Any]:
    merged = {}
    by_name_uid = {}

    for uid, info in data.items():
        if not isinstance(info, dict):
            continue

        base = canonical_name(info.get("base_name", uid))
        if not base:
            continue

        if base not in by_name_uid:
            by_name_uid[base] = uid
            merged[uid] = {
                "user_id": uid,
                "base_name": base,
                "total": int(info.get("total", 0) or 0),
                "working": bool(info.get("working", False)),
                "start": int(info.get("start", 0) or 0),
            }
            continue

        target_uid = by_name_uid[base]
        target = merged[target_uid]

        target["total"] += int(info.get("total", 0) or 0)

        if bool(info.get("working", False)):
            target["working"] = True
            start = int(info.get("start", 0) or 0)
            old_start = int(target.get("start", 0) or 0)
            if old_start == 0:
                target["start"] = start
            elif start > 0:
                target["start"] = min(old_start, start)

        if str(target_uid).startswith("legacy::") and not str(uid).startswith("legacy::"):
            merged[uid] = merged.pop(target_uid)
            merged[uid]["user_id"] = uid
            by_name_uid[base] = uid

    return merged


def load_attendance() -> Dict[str, Any]:
    data = migrate_attendance(load_json(ATTENDANCE_FILE, INITIAL_ATTENDANCE))
    data = merge_same_person_attendance(data)
    save_attendance(data)
    return data


def save_attendance(data: Dict[str, Any]):
    atomic_save_json(ATTENDANCE_FILE, data)


def ensure_attendance_user(member: discord.Member, data: Dict[str, Any]):
    uid = str(member.id)
    base_name = canonical_name(member.display_name)

    if uid in data:
        data[uid]["base_name"] = base_name
        return

    legacy_keys = []
    for key, info in data.items():
        if not isinstance(info, dict):
            continue
        info_name = canonical_name(info.get("base_name", key))
        if names_match(base_name, info_name):
            legacy_keys.append(key)

    if not legacy_keys:
        data[uid] = make_attendance_entry(uid, base_name, 0, False, 0)
        return

    merged_total = 0
    merged_working = False
    merged_start = 0

    for key in legacy_keys:
        info = data.get(key, {})
        merged_total += int(info.get("total", 0) or 0)

        if bool(info.get("working", False)):
            merged_working = True
            start = int(info.get("start", 0) or 0)
            if merged_start == 0:
                merged_start = start
            elif start > 0:
                merged_start = min(merged_start, start)

    data[uid] = make_attendance_entry(uid, base_name, merged_total, merged_working, merged_start)

    for key in legacy_keys:
        if key != uid and key in data:
            del data[key]


async def send_record_embed(is_clock_in: bool, member: discord.Member, elapsed: int = 0):
    ch = bot.get_channel(RECORD_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        return

    title = "🟢 출근" if is_clock_in else "🔴 퇴근"
    color = 0x2ECC71 if is_clock_in else 0xE74C3C

    desc = (
        f"## {title}\n\n"
        f"**관리자**\n{member.mention}\n\n"
        f"**시간**\n{format_kst()}"
    )

    if not is_clock_in:
        desc += f"\n\n**근무시간**\n{format_seconds(elapsed)}"

    embed = discord.Embed(description=desc, color=color)
    await ch.send(embed=embed)


def build_status_embed(data: Dict[str, Any]) -> discord.Embed:
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
        base_name = canonical_name(member.display_name)

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
        ensure_attendance_user(member, data)
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
        data[uid]["base_name"] = canonical_name(member.display_name)
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
def make_promo_entry(uid: str, base_name: str, count: int = 0) -> dict:
    return {
        "user_id": str(uid),
        "base_name": canonical_name(base_name),
        "count": int(count),
    }


def migrate_promo(raw: Dict[str, Any]) -> Dict[str, Any]:
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
        if not isinstance(value, dict):
            continue

        uid = str(value.get("user_id") or key)
        base_name = canonical_name(value.get("base_name", key))
        count = int(value.get("count", 0) or 0)

        if not base_name or is_excluded(base_name):
            continue

        if uid not in migrated:
            migrated[uid] = make_promo_entry(uid, base_name, count)
        else:
            migrated[uid]["count"] += count

    return migrated


def merge_same_person_promo(data: Dict[str, Any]) -> Dict[str, Any]:
    merged = {"__meta__": data.get("__meta__", {"counted_messages": {}, "last_recount_at": 0})}
    by_name_uid = {}

    for uid, info in data.items():
        if uid == "__meta__":
            continue
        if not isinstance(info, dict):
            continue

        base = canonical_name(info.get("base_name", uid))
        if not base:
            continue

        if base not in by_name_uid:
            by_name_uid[base] = uid
            merged[uid] = {
                "user_id": uid,
                "base_name": base,
                "count": int(info.get("count", 0) or 0),
            }
            continue

        target_uid = by_name_uid[base]
        target = merged[target_uid]
        target["count"] += int(info.get("count", 0) or 0)

        if str(target_uid).startswith("legacy::") and not str(uid).startswith("legacy::"):
            merged[uid] = merged.pop(target_uid)
            merged[uid]["user_id"] = uid
            by_name_uid[base] = uid

    return merged


def load_promo() -> Dict[str, Any]:
    data = migrate_promo(load_json(PROMO_FILE, INITIAL_PROMO))
    data = merge_same_person_promo(data)
    save_promo(data)
    return data


def save_promo(data: Dict[str, Any]):
    atomic_save_json(PROMO_FILE, data)


def ensure_promo_meta(data: Dict[str, Any]):
    if "__meta__" not in data or not isinstance(data["__meta__"], dict):
        data["__meta__"] = {"counted_messages": {}, "last_recount_at": 0}
    if "counted_messages" not in data["__meta__"] or not isinstance(data["__meta__"]["counted_messages"], dict):
        data["__meta__"]["counted_messages"] = {}
    if "last_recount_at" not in data["__meta__"]:
        data["__meta__"]["last_recount_at"] = 0


def ensure_promo_user(member: discord.Member, data: Dict[str, Any]):
    uid = str(member.id)
    base_name = canonical_name(member.display_name)

    if uid in data:
        data[uid]["base_name"] = base_name
        return

    legacy_keys = []
    for key, info in data.items():
        if key == "__meta__":
            continue
        if not isinstance(info, dict):
            continue
        info_name = canonical_name(info.get("base_name", key))
        if names_match(base_name, info_name):
            legacy_keys.append(key)

    if not legacy_keys:
        data[uid] = make_promo_entry(uid, base_name, 0)
        return

    merged_count = 0
    old_message_owner_ids = set()

    for key in legacy_keys:
        info = data.get(key, {})
        merged_count += int(info.get("count", 0) or 0)
        old_message_owner_ids.add(str(info.get("user_id", key)))

    data[uid] = make_promo_entry(uid, base_name, merged_count)

    for key in legacy_keys:
        if key != uid and key in data:
            del data[key]

    ensure_promo_meta(data)
    for msg_id, msg_info in list(data["__meta__"]["counted_messages"].items()):
        msg_uid = str(msg_info.get("user_id", ""))
        if msg_uid in old_message_owner_ids:
            data["__meta__"]["counted_messages"][msg_id]["user_id"] = uid


def iter_promo_users(data: Dict[str, Any]):
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


def build_promo_rank_content(data: Dict[str, Any]) -> str:
    sorted_items = sorted(
        list(iter_promo_users(data)),
        key=lambda x: (-int(x[1].get("count", 0)), canonical_name(x[1].get("base_name", "")))
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

    base = load_promo()
    ensure_promo_meta(base)

    if full_reset:
        base = json.loads(json.dumps(INITIAL_PROMO))
        ensure_promo_meta(base)
        base = merge_same_person_promo(base)

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
        base_name = canonical_name(getattr(message.author, "display_name", message.author.name))

        if is_excluded(base_name):
            continue

        member = message.author if isinstance(message.author, discord.Member) else None
        if member:
            ensure_promo_user(member, base)

        if uid not in base:
            # 같은 이름 legacy가 있을 수도 있으니 한 번 더 확인
            matched_uid = None
            for key, info in base.items():
                if key == "__meta__":
                    continue
                if names_match(base_name, info.get("base_name", key)):
                    matched_uid = key
                    break

            if matched_uid and matched_uid != uid:
                old = base.pop(matched_uid)
                base[uid] = make_promo_entry(uid, base_name, int(old.get("count", 0) or 0))
            else:
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
    data[uid]["base_name"] = canonical_name(user.display_name)
    save_attendance(data)

    await interaction.response.send_message(
        f"강제퇴근 완료: {build_member_label(user)} / 추가 반영 {format_seconds(elapsed)}",
        ephemeral=True
    )
    await send_log(f"🛠 강제퇴근 | {build_member_label(user)} (+{format_seconds(elapsed)})")
    await refresh_status_message()


@bot.tree.command(name="근무시간추가", description="근무시간 추가")
@app_commands.describe(user="대상 유저", hours="추가할 시간(예: 12)")
async def add_work_time(interaction: discord.Interaction, user: discord.Member, hours: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)
    if hours <= 0:
        return await interaction.response.send_message("1시간 이상 입력해주세요.", ephemeral=True)

    data = load_attendance()
    ensure_attendance_user(user, data)
    uid = str(user.id)

    data[uid]["total"] = int(data[uid].get("total", 0)) + (hours * 3600)
    data[uid]["base_name"] = canonical_name(user.display_name)
    save_attendance(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 근무시간 {hours}시간 추가 완료",
        ephemeral=True
    )
    await send_log(f"🛠 근무시간추가 | {build_member_label(user)} (+{hours}시간)")
    await refresh_status_message()


@bot.tree.command(name="근무시간차감", description="근무시간 차감")
@app_commands.describe(user="대상 유저", hours="차감할 시간(예: 3)")
async def remove_work_time(interaction: discord.Interaction, user: discord.Member, hours: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)
    if hours <= 0:
        return await interaction.response.send_message("1시간 이상 입력해주세요.", ephemeral=True)

    data = load_attendance()
    ensure_attendance_user(user, data)
    uid = str(user.id)

    data[uid]["total"] = max(0, int(data[uid].get("total", 0)) - (hours * 3600))
    data[uid]["base_name"] = canonical_name(user.display_name)
    save_attendance(data)

    await interaction.response.send_message(
        f"{build_member_label(user)} 근무시간 {hours}시간 차감 완료",
        ephemeral=True
    )
    await send_log(f"🛠 근무시간차감 | {build_member_label(user)} (-{hours}시간)")
    await refresh_status_message()


@bot.tree.command(name="근무초기화", description="근무시간 0으로 초기화")
@app_commands.describe(user="초기화할 유저")
async def reset_work_time(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    data = load_attendance()
    uid = str(user.id)
    data[uid] = make_attendance_entry(uid, canonical_name(user.display_name), 0, False, 0)
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
        removed = True

    if uid in promo:
        del promo[uid]
        removed = True

    ensure_promo_meta(promo)
    for msg_id, msg_info in list(promo["__meta__"]["counted_messages"].items()):
        if str(msg_info.get("user_id", "")) == uid:
            del promo["__meta__"]["counted_messages"][msg_id]

    if not removed:
        return await interaction.response.send_message("삭제할 데이터가 없습니다.", ephemeral=True)

    save_attendance(attendance)
    save_promo(promo)

    await interaction.response.send_message(f"{build_member_label(user)} 퇴사처리 완료", ephemeral=True)
    await send_log(f"🛠 퇴사처리 | {build_member_label(user)}")
    await send_promo_log(f"🛠 퇴사처리 | {build_member_label(user)}")
    await refresh_status_message()
    await refresh_promo_rank_message()


@bot.tree.command(name="퇴사처리이름", description="서버에 없는 사람도 이름으로 출퇴근/홍보 데이터 삭제")
@app_commands.describe(name="삭제할 닉네임 또는 이름")
async def resign_user_by_name(interaction: discord.Interaction, name: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("권한 없음", ephemeral=True)

    target = str(name).strip()
    attendance = load_attendance()
    promo = load_promo()

    removed_attendance = []
    removed_promo = []
    removed_names = set()

    for uid, info in list(attendance.items()):
        base_name = str(info.get("base_name", ""))
        label_name = get_label_from_uid_or_name(uid, base_name)
        if names_match(target, base_name) or names_match(target, label_name):
            removed_attendance.append(uid)
            removed_names.add(base_name)
            del attendance[uid]

    for uid, info in list(promo.items()):
        if uid == "__meta__":
            continue
        base_name = str(info.get("base_name", ""))
        label_name = get_label_from_uid_or_name(uid, base_name)
        if names_match(target, base_name) or names_match(target, label_name):
            removed_promo.append(uid)
            removed_names.add(base_name)
            del promo[uid]

    ensure_promo_meta(promo)
    for msg_id, msg_info in list(promo["__meta__"]["counted_messages"].items()):
        msg_uid = str(msg_info.get("user_id", ""))
        if msg_uid in removed_promo:
            del promo["__meta__"]["counted_messages"][msg_id]

    if not removed_attendance and not removed_promo:
        return await interaction.response.send_message(
            f"`{target}` 과 일치하는 데이터가 없습니다.",
            ephemeral=True
        )

    save_attendance(attendance)
    save_promo(promo)

    removed_text = ", ".join(sorted({canonical_name(x) for x in removed_names if x})) or target

    await interaction.response.send_message(
        f"퇴사처리 완료: {removed_text}",
        ephemeral=True
    )
    await send_log(f"🛠 퇴사처리(이름) | 입력:{target} | 삭제:{removed_text}")
    await send_promo_log(f"🛠 퇴사처리(이름) | 입력:{target} | 삭제:{removed_text}")
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

            uid = str(message.author.id)
            base_name = canonical_name(getattr(message.author, "display_name", message.author.name))

            if not is_excluded(base_name):
                if isinstance(message.author, discord.Member):
                    ensure_promo_user(message.author, data)
                    uid = str(message.author.id)

                msg_id = str(message.id)
                if msg_id not in data["__meta__"]["counted_messages"]:
                    if uid not in data:
                        # 혹시 member가 아닌 경우 대비
                        matched_uid = None
                        for key, info in data.items():
                            if key == "__meta__":
                                continue
                            if names_match(base_name, info.get("base_name", key)):
                                matched_uid = key
                                break

                        if matched_uid and matched_uid != uid:
                            old = data.pop(matched_uid)
                            data[uid] = make_promo_entry(uid, base_name, int(old.get("count", 0) or 0))
                        else:
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

    load_attendance()
    load_promo()

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
