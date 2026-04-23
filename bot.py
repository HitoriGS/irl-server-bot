import asyncio
import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands

from file_generator import generate_config_json, generate_env_file, generate_obs_json
from vultr_api import VultrAPI

# ── 設定 ───────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

VULTR_REFERRAL   = "https://www.vultr.com/?ref=9097831"
TWITCH_TOKEN_URL = "https://twitchtokengenerator.com/"
SPEED_TEST_URL   = "https://cloud.feitsui.com/zh-hant/vultr"
NOALBS_URL       = "https://github.com/NOALBS/nginx-obs-automatic-low-bitrate-switching/releases"
VULTR_API_GUIDE  = "https://www.notion.so/hitorigs/Vultr-API-34bf0e91ede080d985b4f9e7935e632b"

REGIONS = {
    "1": ("🇯🇵 日本 東京",   "nrt"),
    "2": ("🇯🇵 日本 大阪",   "osk"),
    "3": ("🇸🇬 新加坡",      "sgp"),
    "4": ("🇰🇷 韓國 首爾",   "icn"),
    "5": ("🇦🇺 澳洲 雪梨",   "syd"),
    "6": ("🇺🇸 美國 洛杉磯", "lax"),
}

# ── Bot 初始化 ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
executor = ThreadPoolExecutor(max_workers=10)

# user_id -> { step, data }
user_states: dict[int, dict] = {}


# ── 工具函式 ───────────────────────────────────────────────────────────────────
def embed(title="", desc="", color=0x5c6bc0) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color)


# ── STEP 處理函式 ──────────────────────────────────────────────────────────────

async def send_welcome(user: discord.User):
    user_states[user.id] = {"step": "awaiting_disclaimer", "data": {}}

    # ── 免責聲明（必須先同意才能繼續）
    e = embed("🎮 IRL 伺服器架設助手", color=0x5c6bc0)
    e.add_field(name="👋 歡迎！", inline=False, value=(
        "我會一步步引導你完成 IRL 直播伺服器架設。\n"
        "整個過程約需 **10–15 分鐘**，請耐心等候。\n\n"
        "在開始之前，請詳閱以下隱私聲明。"
    ))
    e.add_field(name="🔒 隱私與免責聲明", inline=False, value=(
        "**資料儲存方式**\n"
        "你所提供的所有個人資訊（包含 Vultr API Key、Twitch OAuth 金鑰、OBS 密碼），"
        "以及機器人自動產生並注入設定檔的伺服器 IP 位址等內容，"
        "**僅存在於你與本機器人的 Discord 私訊對話中**，"
        "不會被儲存至任何資料庫、伺服器或第三方服務。\n\n"
        "**使用者責任**\n"
        "上述所有機敏資訊（API Key、OAuth 金鑰、伺服器 IP 等）請務必**妥善保管、切勿外流**。"
        "一旦資訊外洩，可能導致他人未經授權控制你的雲端伺服器或 Twitch 帳號，"
        "進而影響你的直播進行。\n\n"
        "**本機器人對因資訊外洩或使用者操作失誤所造成的任何損失，不承擔任何責任。**"
    ))
    e.add_field(name="✅ 如何繼續", inline=False, value=(
        "閱讀並同意以上聲明後，請輸入 `同意` 繼續。\n"
        "輸入 `取消` 可中止流程。"
    ))
    e.set_footer(text="本機器人由 hitorigs 開發，僅供 IRL 實況伺服器架設使用。")
    await user.send(embed=e)


async def handle_disclaimer(message: discord.Message, state: dict):
    text = message.content.strip()
    if text == "取消":
        user_states.pop(message.author.id, None)
        await message.channel.send("❌ 已取消。如需重新開始，請在伺服器使用 `/irlsetup`。")
        return
    if text != "同意":
        await message.channel.send("請輸入 `同意` 表示同意聲明並繼續，或輸入 `取消` 中止。")
        return

    # 同意後進入 STEP 1
    state["step"] = "awaiting_vultr_key"
    e = embed("✅ 已確認聲明，開始設定！", color=0x43a047)
    e.add_field(name="STEP 1 ── 註冊 Vultr 並取得 API Key", inline=False, value=(
        f"請透過以下推薦連結註冊帳號（方案 $6 USD/月）：\n"
        f"👉 {VULTR_REFERRAL}\n\n"
        f"註冊完成後，請參考以下圖文教學取得 API Key：\n"
        f"📖 {VULTR_API_GUIDE}\n\n"
        f"取得 API Key 後貼給我。"
    ))
    e.add_field(name="⚠️ 重要：不要設定 IP 白名單", inline=False, value=(
        "建立 API Key 時，頁面下方有一個 **Access Control List**。\n"
        "**請保持空白，不要填入任何 IP 位址。**\n\n"
        "如果填了 IP 限制，機器人將無法建立伺服器，導致設定流程失敗。"
    ))
    await message.channel.send(embed=e)


async def handle_vultr_key(message: discord.Message, state: dict):
    api_key = message.content.strip()
    await message.channel.send("⏳ 正在驗證 API Key...")
    loop = asyncio.get_event_loop()
    valid = await loop.run_in_executor(executor, VultrAPI(api_key).validate_key)
    if not valid:
        await message.channel.send("❌ API Key 無效，請確認後重新貼上。")
        return
    state["data"]["vultr_key"] = api_key
    state["step"] = "awaiting_region"
    region_list = "\n".join(f"`{k}` — {v[0]}" for k, v in REGIONS.items())
    e = embed("✅ API Key 驗證成功！", color=0x43a047)
    e.add_field(name="STEP 2 ── 選擇伺服器地區", inline=False, value=(
        f"請先到以下網址測速，選擇延遲最低的地區：\n"
        f"🌐 {SPEED_TEST_URL}\n\n"
        f"測速完成後輸入對應數字：\n\n{region_list}"
    ))
    await message.channel.send(embed=e)


async def handle_region(message: discord.Message, state: dict):
    choice = message.content.strip()
    if choice not in REGIONS:
        await message.channel.send("❌ 請輸入 1–6 之間的數字。")
        return
    name, region_id = REGIONS[choice]
    state["data"]["region_name"] = name
    state["data"]["region_id"]   = region_id
    state["step"] = "awaiting_twitch_id"
    e = embed(color=0x43a047)
    e.add_field(name=f"✅ 已選擇：{name}", inline=False, value=(
        "**STEP 3 ── Twitch 頻道 ID**\n"
        "請輸入你的 Twitch 頻道名稱（小寫英文，不含 @）：\n"
        "例如：`hitorigs`"
    ))
    await message.channel.send(embed=e)


async def handle_twitch_id(message: discord.Message, state: dict):
    tid = message.content.strip().lower().lstrip("@")
    if not all(c.isalnum() or c == "_" for c in tid) or not tid:
        await message.channel.send("❌ Twitch ID 格式不正確，請重新輸入（只能含英數字與底線）。")
        return
    state["data"]["twitch_id"] = tid
    state["step"] = "awaiting_twitch_oauth"
    e = embed(color=0x9146ff)
    e.add_field(name="STEP 4 ── Twitch OAuth 金鑰", inline=False, value=(
        f"請前往以下網址取得 OAuth Token：\n"
        f"👉 {TWITCH_TOKEN_URL}\n\n"
        f"**步驟：**\n"
        f"1. 點選 **Bot Chat Token**\n"
        f"2. 使用你的 Twitch 帳號授權登入\n"
        f"3. 複製 **ACCESS TOKEN**（綠色那串文字）\n"
        f"4. 貼給我（不需要加 `oauth:` 前綴，我會自動處理）"
    ))
    await message.channel.send(embed=e)


async def handle_twitch_oauth(message: discord.Message, state: dict):
    token = message.content.strip()
    if token.lower().startswith("oauth:"):
        token = token[6:]
    state["data"]["twitch_oauth"] = token
    state["step"] = "awaiting_obs_password"
    e = embed(color=0x43a047)
    e.add_field(name="STEP 5 ── OBS WebSocket 密碼", inline=False, value=(
        "NOALBS 需透過 OBS WebSocket 控制場景切換。\n\n"
        "請到 OBS → **工具** → **WebSocket 伺服器設定** → 查看或設定密碼\n\n"
        "請輸入你的 OBS WebSocket 密碼："
    ))
    await message.channel.send(embed=e)


async def handle_obs_password(message: discord.Message, state: dict):
    state["data"]["obs_password"] = message.content.strip()
    state["step"] = "awaiting_obs_port"
    e = embed(color=0x43a047)
    e.add_field(name="STEP 6 ── OBS WebSocket Port", inline=False, value=(
        "請到 OBS → **工具** → **WebSocket 伺服器設定** → 查看伺服器連接埠\n\n"
        "預設為 `4455`，如果你沒有更改過，直接輸入 `4455` 即可。"
    ))
    await message.channel.send(embed=e)


async def handle_obs_port(message: discord.Message, state: dict):
    port_str = message.content.strip()
    if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
        await message.channel.send("❌ Port 格式不正確，請輸入一個數字（例如 `4455`）。")
        return
    state["data"]["obs_port"] = int(port_str)
    state["step"] = "confirming"
    d = state["data"]
    e = embed("📋 請確認以下資料", color=0xff9800)
    e.add_field(name="伺服器地區",   value=d["region_name"],                            inline=True)
    e.add_field(name="Twitch ID",    value=d["twitch_id"],                              inline=True)
    e.add_field(name="OAuth Token",  value=f'`{d["twitch_oauth"][:8]}...`（已遮罩）',  inline=True)
    e.add_field(name="OBS 密碼",     value=f'`{d["obs_password"][:3]}...`（已遮罩）',  inline=True)
    e.add_field(name="OBS Port",     value=f'`{d["obs_port"]}`',                       inline=True)
    e.add_field(name="⚠️ 確認後將開始自動部署", inline=False, value=(
        "預計花費 **10–15 分鐘**，期間請保持私訊開啟。\n\n"
        "輸入 `確認` 開始 ／ `取消` 中止"
    ))
    await message.channel.send(embed=e)


async def handle_confirmation(message: discord.Message, state: dict):
    text = message.content.strip()
    if text == "取消":
        user_states.pop(message.author.id, None)
        await message.channel.send("❌ 已取消。如需重新開始，請在伺服器使用 `/irlsetup`。")
        return
    if text != "確認":
        await message.channel.send("請輸入 `確認` 或 `取消`。")
        return
    state["step"] = "deploying"
    await message.channel.send("🚀 **開始部署！** 我會隨時回報進度，請稍候...")
    asyncio.create_task(run_deployment(message.author, state))


# ── 部署流程 ───────────────────────────────────────────────────────────────────

async def run_deployment(user: discord.User, state: dict):
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str] = asyncio.Queue()

    def progress(msg: str):
        asyncio.run_coroutine_threadsafe(queue.put(msg), loop)

    future = loop.run_in_executor(executor, lambda: _deploy_blocking(state["data"], progress))

    # 持續轉發進度訊息
    while not future.done():
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=0.5)
            await user.send(msg)
        except asyncio.TimeoutError:
            pass

    # 清空剩餘訊息
    while not queue.empty():
        await user.send(queue.get_nowait())

    try:
        result = future.result()
        await send_completion(user, result)
    except Exception as exc:
        logger.exception("Deployment failed")
        await user.send(
            f"❌ **部署過程中發生錯誤：**\n```{exc}```\n"
            "請稍後重試，或至伺服器回報問題。"
        )
    finally:
        user_states.pop(user.id, None)


def _deploy_blocking(data: dict, progress) -> dict:
    """在執行緒中跑的阻塞式部署邏輯（Startup Script 版）。"""
    import time
    vultr = VultrAPI(data["vultr_key"])

    progress("🔍 查詢 Ubuntu 22.04 OS ID...")
    os_id = vultr.get_ubuntu_os_id()

    instance_id = None
    try:
        progress(f"🖥️ 正在 {data['region_name']} 建立伺服器（約 1–2 分鐘）...")
        instance    = vultr.create_instance(data["region_id"], os_id)
        instance_id = instance["id"]

        progress("⏳ 等待伺服器啟動...")
        server_ip = vultr.wait_for_active(instance_id)
        progress(f"✅ 伺服器啟動完成！IP：`{server_ip}`")

        progress("⚙️ 伺服器正在背景自動安裝 Docker 與啟動容器（約 3–5 分鐘後即可使用）...")

        progress("📝 正在產生設定檔...")
        return {
            "server_ip":    server_ip,
            "twitch_id":    data["twitch_id"],
            "twitch_oauth": data["twitch_oauth"],
            "obs_password": data["obs_password"],
            "obs_port":     data["obs_port"],
            "vultr_key":    data["vultr_key"],
        }

    except Exception:
        if instance_id:
            vultr.delete_instance(instance_id)
        raise


async def send_completion(user: discord.User, result: dict):
    ip      = result["server_ip"]
    tid     = result["twitch_id"]
    oauth   = result["twitch_oauth"]
    obs_pw  = result["obs_password"]
    obs_port = result["obs_port"]

    srt_push = f"srtla://{ip}:5000?streamid=live/stream/belabox"
    srt_pull = f"srt://{ip}:8282?streamid=play/stream/belabox"

    # 1. 摘要 embed
    e = embed("🎉 IRL 伺服器架設完成！", color=0x43a047)
    e.add_field(name="📡 推流位址（手機 App 使用）",    value=f"```{srt_push}```", inline=False)
    e.add_field(name="🎬 拉流位址（OBS 媒體來源）",     value=f"```{srt_pull}```", inline=False)
    e.add_field(name="🖥️ 伺服器 IP",                   value=f"`{ip}`",           inline=True)
    e.add_field(name="💰 月費",                         value="約 $6 USD",         inline=True)
    e.add_field(
        name="🔑 Vultr API Key（點擊顯示）",
        value=f"||`{result['vultr_key']}`||",
        inline=False,
    )
    e.add_field(
        name="💡 提示",
        value="未來如需刪除伺服器，請回到 HitoriGS 的 Discord 伺服器使用 `/irldelete` 指令，並回到此訊息點開 API Key 貼上。",
        inline=False,
    )
    await user.send(embed=e)

    # 2. 產生設定檔
    config_json = generate_config_json(tid, ip, obs_pw, obs_port)
    env_content = generate_env_file(tid, oauth)
    obs_json    = generate_obs_json(ip)

    # 3. NOALBS 安裝說明 + config.json / .env
    e2 = embed("📥 STEP 1 ── 安裝 NOALBS", color=0x1565c0)
    e2.add_field(name="下載連結", value=NOALBS_URL, inline=False)
    e2.add_field(name="安裝步驟", inline=False, value=(
        "1. 前往上方連結，下載最新版本，依你的系統選擇對應的 `.zip`：\n"
        "　　🪟 Windows：`x86_64-windows`\n"
        "　　🍎 Mac（M1 以後）：`aarch64-apple`\n"
        "　　🍎 Mac（Intel）：`x86_64-apple`\n"
        "2. 解壓縮後，將下方附上的 `config.json` 和 `.env` **覆蓋**放入資料夾\n"
        "3. 完成！"
    ))
    e2.add_field(name="⚠️ 注意：`.env` 檔案重新命名", inline=False, value=(
        "下載下來的 `.env` 檔案，**檔名會顯示為 `env`（沒有點）**。\n"
        "放入資料夾前，請先將檔名改回 **`.env`**（加上開頭的點）。"
    ))
    await user.send(embed=e2)
    await user.send(
        content="⬇️ **請下載以下兩個檔案：**",
        files=[
            discord.File(io.BytesIO(config_json.encode()), filename="config.json"),
            discord.File(io.BytesIO(env_content.encode()), filename=".env"),
        ],
    )

    # 4. OBS 場景集匯入說明 + IRL.json
    e3 = embed("🎬 STEP 2 ── 匯入 OBS 場景集", color=0x1565c0)
    e3.add_field(name="場景集資料夾路徑", inline=False, value=(
        "**Windows：**\n`%APPDATA%\\obs-studio\\basic\\scenes\\`\n\n"
        "**Mac：**\n`~/Library/Application Support/obs-studio/basic/scenes/`"
    ))
    e3.add_field(name="匯入步驟", inline=False, value=(
        "1. 將下方附上的 `IRL.json` 放入上方資料夾\n"
        "2. 開啟 OBS → 上方選單 **場景集** → **匯入**\n"
        "3. 選擇 `IRL.json` 匯入\n"
        "4. 再次點 **場景集** → 切換到 **IRL**"
    ))
    await user.send(embed=e3)
    await user.send(
        content="⬇️ **請下載以下檔案：**",
        files=[
            discord.File(io.BytesIO(obs_json.encode()), filename="IRL.json"),
        ],
    )

    # 5. 開台流程提示
    e4 = embed("▶️ STEP 3 ── 每次開台的流程", color=0x1565c0)
    e4.add_field(name="開台前必做", inline=False, value=(
        "1. 開啟 **OBS**（確認場景集為 IRL）\n"
        "2. 開啟 **NOALBS**（執行 `noalbs.exe`）\n"
        "3. 在聊天室輸入 `!start` 開始實況\n"
        "4. 手機 App 輸入推流位址開始推流\n\n"
        "⚠️ OBS 和 NOALBS **兩個都要開**，缺一不可！"
    ))
    await user.send(embed=e4)

    # 6. NOALBS 聊天室指令
    e5 = embed("💬 NOALBS 聊天室指令", color=0x6a1b9a)
    e5.add_field(name="可用指令", inline=False, value=(
        "以下指令可在 Twitch 聊天室直接輸入：\n\n"
        "`!b` — 查詢目前推流 Bitrate\n"
        "`!ss`（或 `!switch`）— 手動切換場景（主播可用）\n"
        "`!r`（或 `!refresh`）— 重新整理連線（管理員可用）\n"
        "`!start` — 手動開始實況（主播可用）\n"
        "`!stop` — 手動停止實況（主播可用）\n\n"
        "NOALBS 也會在場景自動切換時於聊天室發送通知訊息。"
    ))
    e5.add_field(name="🚌 揪團出遊時自動停播", inline=False, value=(
        "當你在 Twitch 對其他頻道發起 **Raid（揪團）** 時，"
        "NOALBS 會偵測到 Raid 動作並**自動停止串流**，"
        "不需要手動回到電腦按停止，非常適合 IRL 結束時直接揪團收台。"
    ))
    await user.send(embed=e5)

    await user.send("🎊 **全部完成！祝你直播順利！** 如有任何問題歡迎回到伺服器詢問。")


# ── 刪除伺服器流程 ─────────────────────────────────────────────────────────────

async def send_delete_welcome(user: discord.User):
    user_states[user.id] = {"step": "delete_awaiting_key", "data": {}}
    e = embed("🗑️ 刪除 IRL 伺服器", color=0xd32f2f)
    e.add_field(name="⚠️ 警告", inline=False, value=(
        "此操作將**永久刪除**你的 Vultr 伺服器，**無法復原**。\n\n"
        "請回到當時機器人傳給你的完成訊息，點開 **Vultr API Key（防劇透）** 後貼過來。"
    ))
    await user.send(embed=e)


async def handle_delete_key(message: discord.Message, state: dict):
    api_key = message.content.strip()
    await message.channel.send("⏳ 正在驗證 API Key 並查詢伺服器...")
    loop = asyncio.get_event_loop()
    vultr = VultrAPI(api_key)
    valid = await loop.run_in_executor(executor, vultr.validate_key)
    if not valid:
        await message.channel.send("❌ API Key 無效，請確認後重新貼上。")
        return

    instances = await loop.run_in_executor(executor, vultr.list_irl_instances)
    if not instances:
        user_states.pop(message.author.id, None)
        await message.channel.send(
            "✅ 此 API Key 帳號下找不到任何 IRL 伺服器，可能已經刪除或從未建立。"
        )
        return

    state["data"]["vultr_key"] = api_key
    state["data"]["instances"]  = instances
    state["step"] = "delete_select"

    e = embed("✅ 找到以下 IRL 伺服器", color=0xff9800)
    lines = []
    for i, inst in enumerate(instances, 1):
        lines.append(f"`{i}` — IP: `{inst['ip']}` ｜ 地區: `{inst['region']}` ｜ 狀態: `{inst['status']}`")
    e.add_field(name="請輸入編號選擇要刪除的伺服器", value="\n".join(lines), inline=False)
    e.add_field(name="", value="輸入 `取消` 中止。", inline=False)
    await message.channel.send(embed=e)


async def handle_delete_select(message: discord.Message, state: dict):
    text = message.content.strip()
    if text == "取消":
        user_states.pop(message.author.id, None)
        await message.channel.send("❌ 已取消刪除。")
        return

    instances = state["data"]["instances"]
    if not text.isdigit() or not (1 <= int(text) <= len(instances)):
        await message.channel.send(f"❌ 請輸入 1–{len(instances)} 之間的數字，或輸入 `取消`。")
        return

    selected = instances[int(text) - 1]
    state["data"]["selected"] = selected
    state["step"] = "delete_confirm_1"

    e = embed("⚠️ 第一道確認", color=0xd32f2f)
    e.add_field(name="你選擇刪除的伺服器", inline=False,
        value=f"IP: `{selected['ip']}` ｜ 地區: `{selected['region']}`")
    e.add_field(name="請輸入以下文字繼續", value="`確認刪除`", inline=False)
    await message.channel.send(embed=e)


async def handle_delete_confirm_1(message: discord.Message, state: dict):
    if message.content.strip() == "取消":
        user_states.pop(message.author.id, None)
        await message.channel.send("❌ 已取消刪除。")
        return
    if message.content.strip() != "確認刪除":
        await message.channel.send("❌ 請輸入 `確認刪除` 繼續，或輸入 `取消` 中止。")
        return

    state["step"] = "delete_confirm_2"
    ip = state["data"]["selected"]["ip"]
    e = embed("⚠️ 第二道確認", color=0xd32f2f)
    e.add_field(name="請輸入伺服器 IP 確認", inline=False,
        value=f"請輸入 `{ip}` 以確認你刪除的是正確的伺服器。")
    await message.channel.send(embed=e)


async def handle_delete_confirm_2(message: discord.Message, state: dict):
    if message.content.strip() == "取消":
        user_states.pop(message.author.id, None)
        await message.channel.send("❌ 已取消刪除。")
        return
    ip = state["data"]["selected"]["ip"]
    if message.content.strip() != ip:
        await message.channel.send(f"❌ IP 不符，請重新輸入 `{ip}`，或輸入 `取消` 中止。")
        return

    state["step"] = "delete_confirm_3"
    e = embed("⚠️ 第三道確認（最終）", color=0xd32f2f)
    e.add_field(name="最後一步", inline=False, value=(
        "此操作**無法復原**。伺服器刪除後，所有資料將永久消失。\n\n"
        "請輸入以下文字確認：\n`我了解此操作無法復原`"
    ))
    await message.channel.send(embed=e)


async def handle_delete_confirm_3(message: discord.Message, state: dict):
    if message.content.strip() == "取消":
        user_states.pop(message.author.id, None)
        await message.channel.send("❌ 已取消刪除。")
        return
    if message.content.strip() != "我了解此操作無法復原":
        await message.channel.send("❌ 請輸入 `我了解此操作無法復原`，或輸入 `取消` 中止。")
        return

    state["step"] = "deleting"
    selected = state["data"]["selected"]
    await message.channel.send(f"🗑️ **正在刪除伺服器 `{selected['ip']}`...**")

    loop = asyncio.get_event_loop()
    vultr = VultrAPI(state["data"]["vultr_key"])
    try:
        await loop.run_in_executor(executor, lambda: vultr.delete_instance(selected["id"]))
        await message.channel.send(
            f"✅ **伺服器 `{selected['ip']}` 已成功刪除。**\n"
            "Vultr 帳單將於本月結算時按比例計算，不會繼續收費。"
        )
    except Exception as exc:
        logger.exception("Delete instance failed")
        await message.channel.send(
            f"❌ 刪除失敗：```{exc}```\n請到 Vultr 後台手動確認並刪除。"
        )
    finally:
        user_states.pop(message.author.id, None)


# ── Discord 事件 ───────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Sync failed: {e}")


@bot.tree.command(name="irldelete", description="刪除你的 IRL 直播伺服器 🗑️")
async def delete_command(interaction: discord.Interaction):
    user = interaction.user
    current_step = user_states.get(user.id, {}).get("step", "")
    if current_step in ("deploying", "deleting"):
        await interaction.response.send_message(
            "⚠️ 目前有操作正在進行中，請等待完成後再試。", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await send_delete_welcome(user)
        await interaction.followup.send("✅ 已收到！請查看我傳給你的 **私訊** 繼續操作。", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ 無法傳送私訊！\n請開啟 **允許來自伺服器成員的私訊** 後再試一次。", ephemeral=True
        )


@bot.tree.command(name="irlsetup", description="開始架設你的 IRL 直播伺服器 🎮")
async def setup_command(interaction: discord.Interaction):
    user = interaction.user
    if user_states.get(user.id, {}).get("step") == "deploying":
        await interaction.response.send_message(
            "⚠️ 你目前已有部署進行中，請等待完成後再試。", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await send_welcome(user)
        await interaction.followup.send("✅ 已收到！請查看我傳給你的 **私訊** 開始設定。", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ 無法傳送私訊！\n請開啟 **允許來自伺服器成員的私訊** 後再試一次。", ephemeral=True
        )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.channel, discord.DMChannel):
        return

    uid = message.author.id
    if uid not in user_states:
        await message.channel.send(
            "請先在伺服器中使用 `/irlsetup` 架設伺服器，或使用 `/irldelete` 刪除伺服器。"
        )
        return

    state = user_states[uid]
    handlers = {
        # 架設流程
        "awaiting_disclaimer":   handle_disclaimer,
        "awaiting_vultr_key":    handle_vultr_key,
        "awaiting_region":       handle_region,
        "awaiting_twitch_id":    handle_twitch_id,
        "awaiting_twitch_oauth": handle_twitch_oauth,
        "awaiting_obs_password": handle_obs_password,
        "awaiting_obs_port":     handle_obs_port,
        "confirming":            handle_confirmation,
        "deploying":             lambda m, s: m.channel.send("⏳ 部署正在進行中，請耐心等候..."),
        # 刪除流程
        "delete_awaiting_key":   handle_delete_key,
        "delete_select":         handle_delete_select,
        "delete_confirm_1":      handle_delete_confirm_1,
        "delete_confirm_2":      handle_delete_confirm_2,
        "delete_confirm_3":      handle_delete_confirm_3,
        "deleting":              lambda m, s: m.channel.send("⏳ 刪除正在進行中，請耐心等候..."),
    }
    handler = handlers.get(state["step"])
    if handler:
        await handler(message, state)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
