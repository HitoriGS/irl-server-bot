# 自架伺服器 NOALBS 引導流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/irlsetup` 流程中新增「已有自己的伺服器」分支，讓已自行架好推流環境的使用者只需提供伺服器 IP，機器人就能產生 NOALBS 設定檔並引導安裝，完全不呼叫 Vultr API、不建立伺服器。

**Architecture:** 在既有的 DM 狀態機（`user_states` + `on_message` 依 `state["step"]` 分派）中插入一個新狀態 `awaiting_setup_mode`（同意聲明後立即詢問），依使用者選擇導向既有的 Vultr 全自動分支或新的 `awaiting_server_ip` 分支。兩分支共用 Twitch ID / OAuth / OBS 密碼 / OBS Port 收集邏輯（僅 STEP 編號依模式動態調整），最終在 `confirming` 步驟依 `state["data"]["mode"]` 分岔：`vultr` 沿用現有 `run_deployment`；`self_hosted` 呼叫新函式 `send_self_hosted_completion` 直接產生設定檔並傳送精簡版安裝引導。

**Tech Stack:** Python 3.11+、discord.py 2.3.2、pytest + pytest-asyncio（新增，本專案首次導入測試）

## Global Constraints

- 語言：所有面向使用者的文字（embed、錯誤訊息）使用繁體中文，技術詞彙（函式名、指令）保持原文
- Git commit：每次 commit **前必須先詢問使用者確認**，不可自動 commit；commit 訊息格式為 `type: 說明`（繁體中文說明）；不可使用 `--no-verify`、`--force` 等危險參數
- 不修改 `/irldelete`、`run_deployment`、`_deploy_blocking`、`vultr_api.py`、`file_generator.py`（沿用現有函式，不變更其邏輯）
- 不驗證自架伺服器 IP 格式，直接信任使用者輸入
- 程式碼註解沿用專案現有極簡風格（原始碼幾乎無註解，只在必要處保留簡短說明）

---

## Task 1: 建立測試環境

專案目前完全沒有測試架構。這個任務建立最小 pytest 套件與可重用的假 Discord 物件，供後續所有任務撰寫單元測試。

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_sanity.py`

**Interfaces:**
- Produces: `tests/conftest.py` 提供 pytest fixture `fake_user`（回傳 `FakeUser` 實例，`.id`、`.display_name`、`.channel`、`async .send(content=None, embed=None, files=None)`）與 `fake_message`（工廠函式 `fake_message(content: str) -> FakeMessage`，回傳的物件有 `.content`、`.author`（即 `fake_user`）、`.channel`（與 `fake_user.channel` 同一物件，`async .send(content=None, embed=None, files=None)` 會把呼叫參數以 dict 形式 append 進 `.sent` list）。後續所有任務的測試都透過這兩個 fixture 建構輸入。

- [ ] **Step 1: 建立 `requirements-dev.txt`**

```
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: 建立 `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: 建立 `tests/__init__.py`（空檔案）**

```python
```

- [ ] **Step 4: 建立 `tests/conftest.py`**

```python
import os

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.pop("LOG_CHANNEL_ID", None)

import pytest


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, embed=None, files=None):
        self.sent.append({"content": content, "embed": embed, "files": files})


class FakeUser:
    def __init__(self, user_id=12345, display_name="tester"):
        self.id = user_id
        self.display_name = display_name
        self.channel = FakeChannel()

    async def send(self, content=None, embed=None, files=None):
        self.channel.sent.append({"content": content, "embed": embed, "files": files})


class FakeMessage:
    def __init__(self, content, author):
        self.content = content
        self.author = author
        self.channel = author.channel


@pytest.fixture
def fake_user():
    return FakeUser()


@pytest.fixture
def fake_message(fake_user):
    def _make(content):
        return FakeMessage(content, fake_user)
    return _make
```

`os.environ.setdefault("DISCORD_TOKEN", ...)` 必須放在 `import bot` 之前執行（`bot.py` 頂層用 `os.environ["DISCORD_TOKEN"]` 讀取，若未設定會在 import 時直接拋錯）。conftest.py 會在 pytest 收集測試前被載入，因此把這行放在 conftest 頂層即可保證所有測試檔案 `import bot` 時環境變數已存在。`LOG_CHANNEL_ID` 特意清除，讓 `send_admin_log` 在測試中直接 no-op（該函式一看到 `LOG_CHANNEL_ID` 為空就會 `return`，不會嘗試呼叫 Discord API）。

- [ ] **Step 5: 建立 `tests/test_sanity.py`**

```python
import bot as bot_module


def test_bot_module_imports():
    assert bot_module.bot is not None
```

- [ ] **Step 6: 安裝依賴並執行測試，確認測試環境可運作**

Run: `pip install -r requirements.txt -r requirements-dev.txt && pytest -q`
Expected: `1 passed`

- [ ] **Step 7: 詢問使用者確認後 commit**

```bash
git add requirements-dev.txt pytest.ini tests/__init__.py tests/conftest.py tests/test_sanity.py
git commit -m "test: 新增 pytest 測試環境與假 Discord 物件"
```

---

## Task 2: 新增「選擇架設方式」分岔（`handle_setup_mode`）

同意免責聲明後，不再直接進入 Vultr Key 收集，而是先問使用者要「全新建立」還是「已有自己的伺服器」。

**Files:**
- Modify: `bot.py:101-129`（`handle_disclaimer`）
- Modify: `bot.py`（在 `handle_disclaimer` 之後新增 `handle_setup_mode`）
- Test: `tests/test_setup_mode.py`

**Interfaces:**
- Consumes: `tests/conftest.py` 的 `fake_user`、`fake_message` fixtures（Task 1）
- Produces:
  - `handle_disclaimer(message, state)`：同意後設定 `state["step"] = "awaiting_setup_mode"`，不再寫入 `state["data"]["mode"]`
  - `handle_setup_mode(message: discord.Message, state: dict) -> None`（新函式）：輸入 `"1"` → `state["data"]["mode"] = "vultr"`、`state["step"] = "awaiting_vultr_key"`；輸入 `"2"` → `state["data"]["mode"] = "self_hosted"`、`state["step"] = "awaiting_server_ip"`；其他輸入 → 狀態不變，回覆提示重新輸入
  - 後續任務（Task 3-6）依賴 `state["data"]["mode"]` 的值為 `"vultr"` 或 `"self_hosted"`

- [ ] **Step 1: 寫失敗測試 `tests/test_setup_mode.py`**

```python
import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_disclaimer_agree_moves_to_setup_mode_selection(fake_message):
    state = {"step": "awaiting_disclaimer", "data": {}}
    msg = fake_message("同意")
    await bot_module.handle_disclaimer(msg, state)
    assert state["step"] == "awaiting_setup_mode"
    last = msg.channel.sent[-1]["embed"]
    assert any("選擇架設方式" in f.name for f in last.fields)


@pytest.mark.asyncio
async def test_setup_mode_choose_vultr(fake_message):
    state = {"step": "awaiting_setup_mode", "data": {}}
    msg = fake_message("1")
    await bot_module.handle_setup_mode(msg, state)
    assert state["data"]["mode"] == "vultr"
    assert state["step"] == "awaiting_vultr_key"
    last = msg.channel.sent[-1]["embed"]
    assert any("Vultr" in f.name for f in last.fields)


@pytest.mark.asyncio
async def test_setup_mode_choose_self_hosted(fake_message):
    state = {"step": "awaiting_setup_mode", "data": {}}
    msg = fake_message("2")
    await bot_module.handle_setup_mode(msg, state)
    assert state["data"]["mode"] == "self_hosted"
    assert state["step"] == "awaiting_server_ip"
    last = msg.channel.sent[-1]["embed"]
    assert any("伺服器 IP" in f.name for f in last.fields)


@pytest.mark.asyncio
async def test_setup_mode_invalid_input_stays_and_warns(fake_message):
    state = {"step": "awaiting_setup_mode", "data": {}}
    msg = fake_message("3")
    await bot_module.handle_setup_mode(msg, state)
    assert state["step"] == "awaiting_setup_mode"
    assert "mode" not in state["data"]
    assert msg.channel.sent[-1]["content"] is not None
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_setup_mode.py -v`
Expected: FAIL — `AttributeError: module 'bot' has no attribute 'handle_setup_mode'`（且 `test_disclaimer_agree_moves_to_setup_mode_selection` 因舊版 `handle_disclaimer` 內容不同而失敗）

- [ ] **Step 3: 修改 `handle_disclaimer`（`bot.py:101-129`）**

將原本函式尾端「同意後進入 STEP 1」區塊：

```python
    # 同意後進入 STEP 1
    state["step"] = "awaiting_vultr_key"
    e = embed("✅ 已確認聲明，開始設定！", color=0x43a047)
    e.add_field(name="STEP 1 ── 註冊 Vultr 並取得 API Key", inline=False, value=(
        f"請透過以下推薦連結註冊帳號（方案 $6 USD/月）：\n"
        f"👉 {VULTR_REFERRAL}\n\n"
        f"註冊帳號需綁定 Paypal 或信用卡\n"
        f"不須預先儲值，可勾選 **I just want to link my credit card.**\n"
        f"伺服器是月結帳單付款\n\n"
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
```

替換為：

```python
    # 同意後選擇架設方式
    state["step"] = "awaiting_setup_mode"
    e = embed("✅ 已確認聲明，開始設定！", color=0x43a047)
    e.add_field(name="🔀 選擇架設方式", inline=False, value=(
        "1️⃣ **全新建立伺服器** — 機器人自動於 Vultr 建立雲端伺服器（約 $6 USD/月）\n"
        "2️⃣ **已有自己的伺服器** — 你已自行架好 SRT Live Server 等推流環境，"
        "機器人僅需你的伺服器 IP，直接引導設定 NOALBS\n\n"
        "請輸入對應數字（`1` 或 `2`）。"
    ))
    await message.channel.send(embed=e)
```

- [ ] **Step 4: 在 `handle_disclaimer` 之後新增 `handle_setup_mode`**

```python
async def handle_setup_mode(message: discord.Message, state: dict):
    choice = message.content.strip()
    if choice == "1":
        state["data"]["mode"] = "vultr"
        state["step"] = "awaiting_vultr_key"
        e = embed(color=0x43a047)
        e.add_field(name="STEP 1 ── 註冊 Vultr 並取得 API Key", inline=False, value=(
            f"請透過以下推薦連結註冊帳號（方案 $6 USD/月）：\n"
            f"👉 {VULTR_REFERRAL}\n\n"
            f"註冊帳號需綁定 Paypal 或信用卡\n"
            f"不須預先儲值，可勾選 **I just want to link my credit card.**\n"
            f"伺服器是月結帳單付款\n\n"
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
        return

    if choice == "2":
        state["data"]["mode"] = "self_hosted"
        state["step"] = "awaiting_server_ip"
        e = embed(color=0x43a047)
        e.add_field(name="STEP 1 ── 你的伺服器 IP", inline=False, value=(
            "請確認你的伺服器已架好 **SRT Live Server** 等推流環境，並開放對應連接埠。\n\n"
            "請輸入你的伺服器 IP 位址："
        ))
        await message.channel.send(embed=e)
        return

    await message.channel.send("請輸入 `1`（全新建立伺服器）或 `2`（已有自己的伺服器）。")
```

放置位置：緊接在 `handle_disclaimer` 函式結束之後、`handle_vultr_key` 定義之前。

- [ ] **Step 5: 執行測試，確認通過**

Run: `pytest tests/test_setup_mode.py -v`
Expected: `4 passed`

- [ ] **Step 6: 詢問使用者確認後 commit**

```bash
git add bot.py tests/test_setup_mode.py
git commit -m "feat: 新增架設方式選擇（全新建立 / 已有伺服器）"
```

---

## Task 3: 新增伺服器 IP 收集（`handle_server_ip`）

**Files:**
- Modify: `bot.py`（在 `handle_setup_mode` 之後新增 `handle_server_ip`）
- Test: `tests/test_server_ip.py`

**Interfaces:**
- Consumes: `state["data"]["mode"] == "self_hosted"`（Task 2 設定）
- Produces: `handle_server_ip(message: discord.Message, state: dict) -> None`：將 `message.content.strip()` 存入 `state["data"]["server_ip"]`，設定 `state["step"] = "awaiting_twitch_id"`。後續任務（Task 6）依賴 `state["data"]["server_ip"]` 存在。

- [ ] **Step 1: 寫失敗測試 `tests/test_server_ip.py`**

```python
import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_handle_server_ip_stores_and_advances(fake_message):
    state = {"step": "awaiting_server_ip", "data": {"mode": "self_hosted"}}
    msg = fake_message("  203.0.113.10  ")
    await bot_module.handle_server_ip(msg, state)
    assert state["data"]["server_ip"] == "203.0.113.10"
    assert state["step"] == "awaiting_twitch_id"
    last = msg.channel.sent[-1]["embed"]
    assert any("Twitch" in f.name for f in last.fields)
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_server_ip.py -v`
Expected: FAIL — `AttributeError: module 'bot' has no attribute 'handle_server_ip'`

- [ ] **Step 3: 新增 `handle_server_ip`**

```python
async def handle_server_ip(message: discord.Message, state: dict):
    state["data"]["server_ip"] = message.content.strip()
    state["step"] = "awaiting_twitch_id"
    e = embed(color=0x43a047)
    e.add_field(name="STEP 2 ── Twitch 頻道 ID", inline=False, value=(
        "請輸入你的 Twitch 頻道名稱（小寫英文，不含 @）：\n"
        "例如：`hitorigs`"
    ))
    await message.channel.send(embed=e)
```

放置位置：緊接在 `handle_setup_mode` 函式結束之後、`handle_vultr_key` 定義之前。

- [ ] **Step 4: 執行測試，確認通過**

Run: `pytest tests/test_server_ip.py -v`
Expected: `1 passed`

- [ ] **Step 5: 詢問使用者確認後 commit**

```bash
git add bot.py tests/test_server_ip.py
git commit -m "feat: 新增自架伺服器 IP 收集步驟"
```

---

## Task 4: STEP 編號依模式動態調整

Vultr 模式比自架模式多兩個前置步驟（Vultr Key、地區選擇 vs. 僅伺服器 IP 一步），因此 Twitch OAuth / OBS 密碼 / OBS Port 這三個提示訊息的「STEP N」編號，自架模式要比 Vultr 模式少 1。

**Files:**
- Modify: `bot.py`（新增 `_step_num` helper；修改 `handle_twitch_id`、`handle_twitch_oauth`、`handle_obs_password`）
- Test: `tests/test_step_numbering.py`

**Interfaces:**
- Consumes: `state["data"]["mode"]`（Task 2）
- Produces: `_step_num(base: int, mode: str) -> int`：`mode == "self_hosted"` 回傳 `base - 1`，否則回傳 `base`

- [ ] **Step 1: 寫失敗測試 `tests/test_step_numbering.py`**

```python
import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_twitch_id_step_number_vultr(fake_message):
    state = {"step": "awaiting_twitch_id", "data": {"mode": "vultr"}}
    msg = fake_message("hitorigs")
    await bot_module.handle_twitch_id(msg, state)
    assert state["data"]["twitch_id"] == "hitorigs"
    assert state["step"] == "awaiting_twitch_oauth"
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 4") for f in last.fields)


@pytest.mark.asyncio
async def test_twitch_id_step_number_self_hosted(fake_message):
    state = {"step": "awaiting_twitch_id", "data": {"mode": "self_hosted"}}
    msg = fake_message("hitorigs")
    await bot_module.handle_twitch_id(msg, state)
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 3") for f in last.fields)


@pytest.mark.asyncio
async def test_twitch_oauth_step_number_vultr(fake_message):
    state = {"step": "awaiting_twitch_oauth", "data": {"mode": "vultr"}}
    msg = fake_message("abc123token")
    await bot_module.handle_twitch_oauth(msg, state)
    assert state["data"]["twitch_oauth"] == "abc123token"
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 5") for f in last.fields)


@pytest.mark.asyncio
async def test_twitch_oauth_step_number_self_hosted(fake_message):
    state = {"step": "awaiting_twitch_oauth", "data": {"mode": "self_hosted"}}
    msg = fake_message("abc123token")
    await bot_module.handle_twitch_oauth(msg, state)
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 4") for f in last.fields)


@pytest.mark.asyncio
async def test_obs_password_step_number_vultr(fake_message):
    state = {"step": "awaiting_obs_password", "data": {"mode": "vultr"}}
    msg = fake_message("mypassword")
    await bot_module.handle_obs_password(msg, state)
    assert state["data"]["obs_password"] == "mypassword"
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 6") for f in last.fields)


@pytest.mark.asyncio
async def test_obs_password_step_number_self_hosted(fake_message):
    state = {"step": "awaiting_obs_password", "data": {"mode": "self_hosted"}}
    msg = fake_message("mypassword")
    await bot_module.handle_obs_password(msg, state)
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 5") for f in last.fields)
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_step_numbering.py -v`
Expected: FAIL — 目前三個函式的 embed 固定寫 `STEP 4`/`STEP 5`/`STEP 6`，`self_hosted` 模式的測試會失敗（`AssertionError`）

- [ ] **Step 3: 新增 `_step_num` helper**

放置在 `handle_disclaimer` 定義之前（「STEP 處理函式」區塊開頭）：

```python
def _step_num(base: int, mode: str) -> int:
    """自架伺服器模式少了 2 個前置步驟（Vultr Key + 地區選擇合併為 1 個 IP 步驟），STEP 編號少 1。"""
    return base - 1 if mode == "self_hosted" else base
```

- [ ] **Step 4: 修改 `handle_twitch_id`**

將：

```python
    state["data"]["twitch_id"] = tid
    state["step"] = "awaiting_twitch_oauth"
    e = embed(color=0x9146ff)
    e.add_field(name="STEP 4 ── Twitch OAuth 金鑰", inline=False, value=(
```

改為：

```python
    state["data"]["twitch_id"] = tid
    state["step"] = "awaiting_twitch_oauth"
    step_num = _step_num(4, state["data"]["mode"])
    e = embed(color=0x9146ff)
    e.add_field(name=f"STEP {step_num} ── Twitch OAuth 金鑰", inline=False, value=(
```

- [ ] **Step 5: 修改 `handle_twitch_oauth`**

將：

```python
    state["data"]["twitch_oauth"] = token
    state["step"] = "awaiting_obs_password"
    e = embed(color=0x43a047)
    e.add_field(name="STEP 5 ── OBS WebSocket 密碼", inline=False, value=(
```

改為：

```python
    state["data"]["twitch_oauth"] = token
    state["step"] = "awaiting_obs_password"
    step_num = _step_num(5, state["data"]["mode"])
    e = embed(color=0x43a047)
    e.add_field(name=f"STEP {step_num} ── OBS WebSocket 密碼", inline=False, value=(
```

- [ ] **Step 6: 修改 `handle_obs_password`**

將：

```python
    state["data"]["obs_password"] = message.content.strip()
    state["step"] = "awaiting_obs_port"
    e = embed(color=0x43a047)
    e.add_field(name="STEP 6 ── OBS WebSocket Port", inline=False, value=(
```

改為：

```python
    state["data"]["obs_password"] = message.content.strip()
    state["step"] = "awaiting_obs_port"
    step_num = _step_num(6, state["data"]["mode"])
    e = embed(color=0x43a047)
    e.add_field(name=f"STEP {step_num} ── OBS WebSocket Port", inline=False, value=(
```

- [ ] **Step 7: 執行測試，確認通過**

Run: `pytest tests/test_step_numbering.py -v`
Expected: `6 passed`

- [ ] **Step 8: 執行全部測試確認沒有回歸**

Run: `pytest -q`
Expected: 全部 PASS

- [ ] **Step 9: 詢問使用者確認後 commit**

```bash
git add bot.py tests/test_step_numbering.py
git commit -m "feat: STEP 編號依架設模式動態調整"
```

---

## Task 5: 確認畫面依模式顯示不同摘要

Vultr 模式維持顯示地區與伺服器規格/月費；自架模式改顯示伺服器 IP，不顯示規格/月費。

**Files:**
- Modify: `bot.py`（`handle_obs_port`）
- Test: `tests/test_confirmation_summary.py`

**Interfaces:**
- Consumes: `state["data"]["mode"]`、`state["data"]["server_ip"]`（self_hosted）或 `state["data"]["region_name"]`／`state["data"]["plan_info"]`（vultr）
- Produces: `handle_obs_port` 在 `state["step"] = "confirming"` 之後送出的 embed 依模式包含不同欄位；`state["data"]["obs_port"]` 寫入行為不變

- [ ] **Step 1: 寫失敗測試 `tests/test_confirmation_summary.py`**

```python
import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_obs_port_confirmation_vultr_shows_region_and_plan(fake_message):
    state = {
        "step": "awaiting_obs_port",
        "data": {
            "mode": "vultr",
            "region_name": "🇯🇵 日本 東京",
            "twitch_id": "hitorigs",
            "twitch_oauth": "abcdefgh12345",
            "obs_password": "secretpw",
            "plan_info": {
                "vcpu_count": 1, "ram": 1024, "disk": 25,
                "bandwidth": 2048, "monthly_cost": 6,
            },
        },
    }
    msg = fake_message("4455")
    await bot_module.handle_obs_port(msg, state)
    assert state["data"]["obs_port"] == 4455
    assert state["step"] == "confirming"
    last = msg.channel.sent[-1]["embed"]
    names = [f.name for f in last.fields]
    assert "伺服器地區" in names
    assert "🖥️ 伺服器規格" in names
    assert "伺服器 IP" not in names


@pytest.mark.asyncio
async def test_obs_port_confirmation_self_hosted_shows_ip_only(fake_message):
    state = {
        "step": "awaiting_obs_port",
        "data": {
            "mode": "self_hosted",
            "server_ip": "203.0.113.10",
            "twitch_id": "hitorigs",
            "twitch_oauth": "abcdefgh12345",
            "obs_password": "secretpw",
        },
    }
    msg = fake_message("4455")
    await bot_module.handle_obs_port(msg, state)
    last = msg.channel.sent[-1]["embed"]
    names = [f.name for f in last.fields]
    assert "伺服器 IP" in names
    assert "伺服器地區" not in names
    assert "🖥️ 伺服器規格" not in names
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_confirmation_summary.py -v`
Expected: FAIL — `self_hosted` 測試會因 `handle_obs_port` 仍嘗試存取不存在的 `d["region_name"]` 而拋 `KeyError`

- [ ] **Step 3: 修改 `handle_obs_port`**

將整段確認 embed 建構邏輯：

```python
    state["data"]["obs_port"] = int(port_str)
    state["step"] = "confirming"
    d = state["data"]
    e = embed("📋 請確認以下資料", color=0xff9800)
    e.add_field(name="伺服器地區",   value=d["region_name"],                            inline=True)
    e.add_field(name="Twitch ID",    value=d["twitch_id"],                              inline=True)
    e.add_field(name="OAuth Token",  value=f'`{d["twitch_oauth"][:8]}...`（已遮罩）',  inline=True)
    e.add_field(name="OBS 密碼",     value=f'`{d["obs_password"][:3]}...`（已遮罩）',  inline=True)
    e.add_field(name="OBS Port",     value=f'`{d["obs_port"]}`',                       inline=True)
    p = state["data"].get("plan_info", {})
    vcpu      = p.get("vcpu_count", "?")
    ram_gb    = round(p["ram"] / 1024) if p.get("ram") else "?"
    disk      = p.get("disk", "?")
    bw_tb     = p["bandwidth"] / 1024 if p.get("bandwidth") else None
    bw_str    = f"{bw_tb:g} TB" if bw_tb and bw_tb >= 1 else (f"{p['bandwidth']} GB" if p.get("bandwidth") else "?")
    cost      = int(p["monthly_cost"]) if p.get("monthly_cost") and p["monthly_cost"] == int(p["monthly_cost"]) else p.get("monthly_cost", "?")
    e.add_field(name="🖥️ 伺服器規格", inline=False, value=(
        f"{vcpu} vCPU・{ram_gb} GB RAM・{disk} GB SSD\n"
        f"每月流量：**{bw_str}**\n"
        f"月費：**${cost} USD／月**（依實際使用天數按比例計算）"
    ))
    e.add_field(name="⚠️ 確認後將開始自動部署", inline=False, value=(
        "預計花費 **10–15 分鐘**，期間請保持私訊開啟。\n\n"
        "輸入 `確認` 開始 ／ `取消` 中止"
    ))
    await message.channel.send(embed=e)
```

改為：

```python
    state["data"]["obs_port"] = int(port_str)
    state["step"] = "confirming"
    d = state["data"]
    e = embed("📋 請確認以下資料", color=0xff9800)
    if d["mode"] == "self_hosted":
        e.add_field(name="伺服器 IP",     value=d["server_ip"],                              inline=True)
    else:
        e.add_field(name="伺服器地區",   value=d["region_name"],                            inline=True)
    e.add_field(name="Twitch ID",    value=d["twitch_id"],                              inline=True)
    e.add_field(name="OAuth Token",  value=f'`{d["twitch_oauth"][:8]}...`（已遮罩）',  inline=True)
    e.add_field(name="OBS 密碼",     value=f'`{d["obs_password"][:3]}...`（已遮罩）',  inline=True)
    e.add_field(name="OBS Port",     value=f'`{d["obs_port"]}`',                       inline=True)
    if d["mode"] == "vultr":
        p = state["data"].get("plan_info", {})
        vcpu      = p.get("vcpu_count", "?")
        ram_gb    = round(p["ram"] / 1024) if p.get("ram") else "?"
        disk      = p.get("disk", "?")
        bw_tb     = p["bandwidth"] / 1024 if p.get("bandwidth") else None
        bw_str    = f"{bw_tb:g} TB" if bw_tb and bw_tb >= 1 else (f"{p['bandwidth']} GB" if p.get("bandwidth") else "?")
        cost      = int(p["monthly_cost"]) if p.get("monthly_cost") and p["monthly_cost"] == int(p["monthly_cost"]) else p.get("monthly_cost", "?")
        e.add_field(name="🖥️ 伺服器規格", inline=False, value=(
            f"{vcpu} vCPU・{ram_gb} GB RAM・{disk} GB SSD\n"
            f"每月流量：**{bw_str}**\n"
            f"月費：**${cost} USD／月**（依實際使用天數按比例計算）"
        ))
        e.add_field(name="⚠️ 確認後將開始自動部署", inline=False, value=(
            "預計花費 **10–15 分鐘**，期間請保持私訊開啟。\n\n"
            "輸入 `確認` 開始 ／ `取消` 中止"
        ))
    else:
        e.add_field(name="⚠️ 確認後將產生設定檔", inline=False, value=(
            "輸入 `確認` 開始 ／ `取消` 中止"
        ))
    await message.channel.send(embed=e)
```

- [ ] **Step 4: 執行測試，確認通過**

Run: `pytest tests/test_confirmation_summary.py -v`
Expected: `2 passed`

- [ ] **Step 5: 詢問使用者確認後 commit**

```bash
git add bot.py tests/test_confirmation_summary.py
git commit -m "feat: 確認畫面依架設模式顯示不同摘要"
```

---

## Task 6: 自架模式的完成流程（`send_self_hosted_completion`）

確認後，自架模式直接產生 NOALBS 設定檔並傳送精簡版安裝引導，不呼叫任何 Vultr API。

**Files:**
- Modify: `bot.py`（`handle_confirmation`；新增 `send_self_hosted_completion`）
- Test: `tests/test_self_hosted_completion.py`

**Interfaces:**
- Consumes: `file_generator.generate_config_json(twitch_id: str, server_ip: str, obs_password: str, obs_port: int) -> str`、`generate_env_file(twitch_id: str, oauth_token: str) -> str`、`generate_obs_json(server_ip: str) -> str`（既有函式，不修改）；`send_admin_log(user: discord.User, action: str) -> None`（既有函式，不修改）
- Produces: `send_self_hosted_completion(user: discord.User, state: dict) -> None`；`handle_confirmation` 依 `state["data"]["mode"]` 分岔，`self_hosted` 分支同步呼叫 `send_self_hosted_completion` 後清除 `user_states[user.id]`

- [ ] **Step 1: 寫失敗測試 `tests/test_self_hosted_completion.py`**

```python
import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_confirmation_self_hosted_generates_files_and_clears_state(fake_user, fake_message):
    bot_module.user_states[fake_user.id] = {
        "step": "confirming",
        "data": {
            "mode": "self_hosted",
            "server_ip": "203.0.113.10",
            "twitch_id": "hitorigs",
            "twitch_oauth": "abcdefgh12345",
            "obs_password": "secretpw",
            "obs_port": 4455,
        },
    }
    state = bot_module.user_states[fake_user.id]
    msg = fake_message("確認")
    await bot_module.handle_confirmation(msg, state)

    assert fake_user.id not in bot_module.user_states
    sent = fake_user.channel.sent
    filenames = [f.filename for item in sent if item.get("files") for f in item["files"]]
    assert "config.json" in filenames
    assert ".env" in filenames
    assert "IRL.json" in filenames


@pytest.mark.asyncio
async def test_send_self_hosted_completion_content(fake_user):
    state = {
        "data": {
            "server_ip": "203.0.113.10",
            "twitch_id": "hitorigs",
            "twitch_oauth": "abcdefgh12345",
            "obs_password": "secretpw",
            "obs_port": 4455,
        }
    }
    await bot_module.send_self_hosted_completion(fake_user, state)
    embeds = [item["embed"] for item in fake_user.channel.sent if item.get("embed")]
    titles = [e.title for e in embeds if e.title]
    assert any("安裝 NOALBS" in t for t in titles)
    assert any("OBS 場景集" in t for t in titles)
    assert not any("伺服器規格" in (f.name or "") for e in embeds for f in e.fields)
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_self_hosted_completion.py -v`
Expected: FAIL — `AttributeError: module 'bot' has no attribute 'send_self_hosted_completion'`

- [ ] **Step 3: 新增 `send_self_hosted_completion`**

放置在 `send_completion` 函式結束之後：

```python
async def send_self_hosted_completion(user: discord.User, state: dict):
    d        = state["data"]
    ip       = d["server_ip"]
    tid      = d["twitch_id"]
    oauth    = d["twitch_oauth"]
    obs_pw   = d["obs_password"]
    obs_port = d["obs_port"]

    srt_push = f"srtla://{ip}:5000?streamid=live/stream/belabox"
    srt_pull = f"srt://{ip}:8282?streamid=play/stream/belabox"

    moblin_url = f"https://hitorigs.live/irl/moblin/?ip={ip}"
    larix_url  = f"https://hitorigs.live/irl/larix/?ip={ip}"

    config_json = generate_config_json(tid, ip, obs_pw, obs_port)
    env_content = generate_env_file(tid, oauth)
    obs_json    = generate_obs_json(ip)

    e1 = embed("📥 STEP 1 ── 安裝 NOALBS", color=0x1565c0)
    e1.add_field(name="下載連結", value=NOALBS_URL, inline=False)
    e1.add_field(name="安裝步驟", inline=False, value=(
        "1. 前往上方連結，下載最新版本，依你的系統選擇對應的 `.zip`：\n"
        "　　🪟 Windows：`x86_64-windows`\n"
        "　　🍎 Mac（M1 以後）：`aarch64-apple`\n"
        "　　🍎 Mac（Intel）：`x86_64-apple`\n"
        "2. 解壓縮後，將下方附上的 `config.json` 和 `.env` **覆蓋**放入資料夾\n"
        "3. 完成！"
    ))
    e1.add_field(name="⚠️ 注意：`.env` 檔案重新命名", inline=False, value=(
        "下載下來的 `.env` 檔案，**檔名會顯示為 `env`（沒有點）**。\n"
        "放入資料夾前，請先將檔名改回 **`.env`**（加上開頭的點）。"
    ))
    await user.send(embed=e1)
    await user.send(
        content="⬇️ **請下載以下兩個檔案：**",
        files=[
            discord.File(io.BytesIO(config_json.encode()), filename="config.json"),
            discord.File(io.BytesIO(env_content.encode()), filename=".env"),
        ],
    )

    e2 = embed("🎬 STEP 2 ── 匯入 OBS 場景集", color=0x1565c0)
    e2.add_field(name="場景集資料夾路徑", inline=False, value=(
        "**Windows：**\n`%APPDATA%\\obs-studio\\basic\\scenes\\`\n\n"
        "**Mac：**\n`~/Library/Application Support/obs-studio/basic/scenes/`"
    ))
    e2.add_field(name="匯入步驟", inline=False, value=(
        "1. 將下方附上的 `IRL.json` 放入上方資料夾\n"
        "2. 開啟 OBS → 上方選單 **場景集** → **匯入**\n"
        "3. 選擇 `IRL.json` 匯入\n"
        "4. 再次點 **場景集** → 切換到 **IRL**"
    ))
    await user.send(embed=e2)
    await user.send(
        content="⬇️ **請下載以下檔案：**",
        files=[
            discord.File(io.BytesIO(obs_json.encode()), filename="IRL.json"),
        ],
    )

    e3 = embed("▶️ STEP 3 ── 每次開台的流程", color=0x1565c0)
    e3.add_field(name="開台前必做", inline=False, value=(
        "1. 開啟 **OBS**（確認場景集為 IRL）\n"
        "2. 開啟 **NOALBS**（執行 `noalbs.exe`）\n"
        "3. 在聊天室輸入 `!start` 開始實況\n"
        "4. 手機 App 輸入推流位址開始推流\n\n"
        "⚠️ OBS 和 NOALBS **兩個都要開**，缺一不可！"
    ))
    await user.send(embed=e3)

    e4 = embed("🎉 設定完成！以下是你的推拉流資訊", color=0x43a047)
    e4.add_field(name="📡 推流位址（手機 App 使用）",    value=f"```{srt_push}```", inline=False)
    e4.add_field(name="📱 手機 App 一鍵設定", inline=False, value=(
        f"[Moblin 點此設定（請使用手機點擊連結）]({moblin_url})\n\n"
        f"[IRL Pro 點此設定（請使用手機點擊連結）]({larix_url})\n"
    ))
    e4.add_field(name="🎬 拉流位址（OBS 媒體來源已自動在場景集內生成，不用再手動填入）", value=f"```{srt_pull}```", inline=False)
    e4.add_field(name="🖥️ 伺服器 IP", value=f"`{ip}`", inline=True)
    await user.send(embed=e4)

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
    await send_admin_log(user, "✅ 自架伺服器設定完成")
```

- [ ] **Step 4: 修改 `handle_confirmation`**

將：

```python
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
```

改為：

```python
async def handle_confirmation(message: discord.Message, state: dict):
    text = message.content.strip()
    if text == "取消":
        user_states.pop(message.author.id, None)
        await message.channel.send("❌ 已取消。如需重新開始，請在伺服器使用 `/irlsetup`。")
        return
    if text != "確認":
        await message.channel.send("請輸入 `確認` 或 `取消`。")
        return

    if state["data"]["mode"] == "self_hosted":
        state["step"] = "completing"
        await message.channel.send("🚀 **產生設定檔中...**")
        await send_self_hosted_completion(message.author, state)
        user_states.pop(message.author.id, None)
        return

    state["step"] = "deploying"
    await message.channel.send("🚀 **開始部署！** 我會隨時回報進度，請稍候...")
    asyncio.create_task(run_deployment(message.author, state))
```

- [ ] **Step 5: 執行測試，確認通過**

Run: `pytest tests/test_self_hosted_completion.py -v`
Expected: `2 passed`

- [ ] **Step 6: 執行全部測試確認沒有回歸**

Run: `pytest -q`
Expected: 全部 PASS

- [ ] **Step 7: 詢問使用者確認後 commit**

```bash
git add bot.py tests/test_self_hosted_completion.py
git commit -m "feat: 自架模式確認後直接產生 NOALBS 設定檔並引導安裝"
```

---

## Task 7: `on_message` 分派表加入新步驟

**Files:**
- Modify: `bot.py`（`on_message` 內的 `handlers` dict）
- Test: `tests/test_step_handlers_dispatch.py`

**Interfaces:**
- Consumes: `handle_setup_mode`（Task 2）、`handle_server_ip`（Task 3）
- Produces: 模組層級常數 `STEP_HANDLERS: dict[str, Callable]`，供 `on_message` 查表分派；後續若有新增步驟，直接在此常數新增 entry 即可

- [ ] **Step 1: 寫失敗測試 `tests/test_step_handlers_dispatch.py`**

```python
import bot as bot_module


def test_step_handlers_includes_new_self_hosted_steps():
    assert bot_module.STEP_HANDLERS["awaiting_setup_mode"] is bot_module.handle_setup_mode
    assert bot_module.STEP_HANDLERS["awaiting_server_ip"] is bot_module.handle_server_ip


def test_step_handlers_still_includes_existing_steps():
    assert bot_module.STEP_HANDLERS["awaiting_vultr_key"] is bot_module.handle_vultr_key
    assert bot_module.STEP_HANDLERS["confirming"] is bot_module.handle_confirmation
    assert bot_module.STEP_HANDLERS["delete_awaiting_key"] is bot_module.handle_delete_key
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_step_handlers_dispatch.py -v`
Expected: FAIL — `AttributeError: module 'bot' has no attribute 'STEP_HANDLERS'`（目前 `handlers` dict 是 `on_message` 內的區域變數，模組層級沒有這個名稱）

- [ ] **Step 3: 將 `on_message` 內的 `handlers` dict 提升為模組層級 `STEP_HANDLERS`**

將現有（`bot.py` 內 `on_message` 函式）：

```python
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
```

改為（在 `on_message` 之前新增模組層級常數 `STEP_HANDLERS`，`on_message` 改用它）：

```python
STEP_HANDLERS = {
    # 架設流程
    "awaiting_disclaimer":   handle_disclaimer,
    "awaiting_setup_mode":   handle_setup_mode,
    "awaiting_vultr_key":    handle_vultr_key,
    "awaiting_region":       handle_region,
    "awaiting_server_ip":    handle_server_ip,
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
    handler = STEP_HANDLERS.get(state["step"])
    if handler:
        await handler(message, state)
```

`STEP_HANDLERS` 必須放在所有被參照的 handler 函式定義之後、`on_message` 定義之前（即緊接在 `handle_delete_confirm_3` 之後）。

- [ ] **Step 4: 執行測試，確認通過**

Run: `pytest tests/test_step_handlers_dispatch.py -v`
Expected: `2 passed`

- [ ] **Step 5: 執行全部測試確認沒有回歸**

Run: `pytest -q`
Expected: 全部 PASS

- [ ] **Step 6: 詢問使用者確認後 commit**

```bash
git add bot.py tests/test_step_handlers_dispatch.py
git commit -m "refactor: 將 on_message 分派表提升為模組層級 STEP_HANDLERS"
```

---

## Task 8: 更新 README 並做最終驗證

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: 無（純文件更新 + 全專案測試驗證）

- [ ] **Step 1: 更新 `README.md` 的「功能」與「指令」段落**

將：

```markdown
## 功能

- 全程私訊引導，無需手動操作伺服器
- 自動在 Vultr 建立雲端伺服器（Ubuntu 22.04，$6 USD/月）
- 自動產生 NOALBS `config.json`、`.env`、OBS 場景集 `IRL.json`
- 支援多地區選擇（日本、新加坡、韓國、澳洲、美國）
- 提供刪除伺服器流程（三道確認防誤刪）

## 指令

| 指令 | 說明 |
|---|---|
| `/irlsetup` | 開始架設 IRL 直播伺服器 |
| `/irldelete` | 刪除已建立的 IRL 直播伺服器 |
```

改為：

```markdown
## 功能

- 全程私訊引導，無需手動操作伺服器
- 支援兩種架設方式：
  - **全新建立伺服器**：自動在 Vultr 建立雲端伺服器（Ubuntu 22.04，$6 USD/月），支援多地區選擇（日本、新加坡、韓國、澳洲、美國）
  - **已有自己的伺服器**：僅需提供伺服器 IP，直接引導設定 NOALBS，不建立任何雲端資源
- 自動產生 NOALBS `config.json`、`.env`、OBS 場景集 `IRL.json`
- 提供刪除伺服器流程（三道確認防誤刪，僅適用於機器人建立的 Vultr 伺服器）

## 指令

| 指令 | 說明 |
|---|---|
| `/irlsetup` | 開始架設 IRL 直播伺服器（可選擇全新建立或使用已有伺服器） |
| `/irldelete` | 刪除已建立的 IRL 直播伺服器（僅限 Vultr 全新建立的伺服器） |
```

- [ ] **Step 2: 執行完整測試套件，確認所有任務累積結果通過**

Run: `pytest -q`
Expected: 全部 PASS（累計應有 Task1 的 1 個 + Task2 的 4 個 + Task3 的 1 個 + Task4 的 6 個 + Task5 的 2 個 + Task6 的 2 個 + Task7 的 2 個 = 18 個測試）

- [ ] **Step 3: 詢問使用者確認後 commit**

```bash
git add README.md
git commit -m "docs: 更新 README 說明自架伺服器架設方式"
```

- [ ] **Step 4: 提醒使用者手動驗證（非自動化步驟）**

由於本專案的 Discord 互動需要真實 Bot Token 與 DM 頻道，pytest 測試已涵蓋所有邏輯分支，但建議使用者在正式環境用 `/irlsetup` 實際走一次「已有自己的伺服器」分支，確認 Discord embed 排版、檔案下載（`config.json`／`.env`／`IRL.json`）在真實用戶端顯示正常。這步驟留給使用者在部署後自行確認，不屬於此計畫的自動化任務。
