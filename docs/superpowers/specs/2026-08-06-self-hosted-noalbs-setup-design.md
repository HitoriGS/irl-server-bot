# 自架伺服器 NOALBS 引導流程 設計文件

日期：2026-08-06

## 背景

目前 `/irlsetup` 是全自動流程：機器人透過 Vultr API 幫使用者建立雲端伺服器、自動安裝 Docker/SRT 環境，並產生 NOALBS `config.json`／`.env` 與 OBS 場景集 `IRL.json`，最後引導使用者完成 NOALBS 安裝與設定。

部分使用者已經自行架好了直播伺服器（自己的 VPS 或本機，已安裝 SRT Live Server / nginx 等環境），不需要機器人幫忙建立伺服器，但仍希望機器人能引導完成 NOALBS 的安裝與設定檔產生。目前的流程沒有這個分支，這些使用者無法使用 `/irlsetup`。

## 目標

在 `/irlsetup` 流程中新增一個分岔：使用者可選擇「全新建立伺服器」（沿用現有 Vultr 全自動流程）或「已有自己的伺服器」（新流程，只需提供伺服器 IP，機器人產生 NOALBS 設定檔並引導安裝，不呼叫 Vultr API、不建立伺服器）。

## 非目標

- 不修改 `/irldelete` 指令與其流程
- 不修改 Vultr 全自動部署邏輯（`run_deployment`、`_deploy_blocking`、`vultr_api.py`）
- 不驗證使用者提供的自架伺服器 IP 是否可連線、是否已正確安裝 SRT Live Server；不做伺服器環境健康檢查
- 不修改 `file_generator.py` 的設定檔產生邏輯

## 流程設計

### 整體狀態機

```
awaiting_disclaimer（同意）
        ↓
awaiting_setup_mode ────────────── 新增
   ├── 輸入 1：全新建立伺服器 → awaiting_vultr_key（現有流程，完全不變）
   └── 輸入 2：已有自己的伺服器 → awaiting_server_ip（新增）
              ↓
       awaiting_server_ip ──────── 新增：收集伺服器 IP，不驗證格式
              ↓
       awaiting_twitch_id ─────┐
       awaiting_twitch_oauth    │ 完全沿用現有函式邏輯，
       awaiting_obs_password    │ 僅 embed 內「STEP N」編號依模式調整
       awaiting_obs_port ───────┘
              ↓
       confirming（自架版摘要：伺服器 IP + Twitch ID + OAuth(遮罩) + OBS密碼(遮罩) + OBS Port，
                   不含伺服器規格／月費）
              ↓
       輸入「確認」→ 直接產生設定檔並顯示精簡完成說明（不呼叫 Vultr API，不建立伺服器）
```

### 1. 模式選擇（`handle_setup_mode`，新函式）

`handle_disclaimer` 中，使用者輸入「同意」後，不再直接進入 `awaiting_vultr_key`，而是進入新的 `awaiting_setup_mode` 狀態，顯示訊息：

```
STEP 1 ── 選擇架設方式

1. 全新建立伺服器（機器人自動於 Vultr 建立，$6 USD/月）
2. 已有自己的伺服器（僅需提供伺服器 IP，機器人引導設定 NOALBS）

請輸入對應數字。
```

新增 `handle_setup_mode(message, state)`：
- 輸入 `1`：`state["data"]["mode"] = "vultr"`，`state["step"] = "awaiting_vultr_key"`，顯示現有 STEP 1（Vultr API Key）內容
- 輸入 `2`：`state["data"]["mode"] = "self_hosted"`，`state["step"] = "awaiting_server_ip"`，顯示新的伺服器 IP 詢問訊息
- 其他輸入：提示重新輸入 `1` 或 `2`

### 2. 伺服器 IP 收集（`handle_server_ip`，新函式）

顯示訊息詢問伺服器 IP（提示使用者需已在該伺服器上架好 SRT Live Server / nginx 等推流環境）。使用者輸入後：
- 僅 `strip()` 空白，**不驗證格式**（可接受 IP 或網域名稱）
- 存入 `state["data"]["server_ip"]`
- `state["step"] = "awaiting_twitch_id"`

### 3. 共用步驟（Twitch ID / OAuth / OBS 密碼 / OBS Port）

`handle_twitch_id`、`handle_twitch_oauth`、`handle_obs_password`、`handle_obs_port` 四個函式的欄位收集邏輯（驗證規則、資料寫入 `state["data"]`）**完全不變**。

唯一調整：embed 中的「STEP N」文字依 `state["data"]["mode"]` 動態產生：
- `mode == "vultr"`：維持現有編號（STEP 3 Twitch ID、STEP 4 OAuth、STEP 5 OBS 密碼、STEP 6 OBS Port）
- `mode == "self_hosted"`：少了 Vultr Key 與地區兩步，編號往前遞補（STEP 2 Twitch ID、STEP 3 OAuth、STEP 4 OBS 密碼、STEP 5 OBS Port）

### 4. 確認畫面（`handle_confirmation`）

依 `state["data"]["mode"]` 分岔：

- **`vultr` 模式**：完全不變，維持現有摘要 embed（伺服器地區、Twitch ID、OAuth、OBS 密碼、OBS Port、伺服器規格、月費），確認後呼叫 `run_deployment`（背景執行緒跑 Vultr API，含進度回報）。
- **`self_hosted` 模式**：顯示簡化摘要 embed（伺服器 IP、Twitch ID、OAuth(遮罩)、OBS 密碼(遮罩)、OBS Port），**不含**伺服器規格／月費欄位。確認後**同步**呼叫新函式 `send_self_hosted_completion(user, state)`（不需要背景執行緒，因為沒有 Vultr API 呼叫，全程只是產生檔案與傳訊息），完成後清除 `user_states`。

### 5. 完成說明（`send_self_hosted_completion`，新函式）

沿用 `file_generator.py` 既有函式（不修改）：
```python
config_json = generate_config_json(tid, server_ip, obs_pw, obs_port)
env_content = generate_env_file(tid, oauth)
obs_json    = generate_obs_json(server_ip)
```

發送內容，對照 `send_completion` 精簡如下：

**保留**：
- STEP 1：NOALBS 安裝說明（下載連結、依系統選擇版本、`config.json`/`.env` 覆蓋放入資料夾）+ 附上 `config.json`、`.env` 檔案
- STEP 2：OBS 場景集匯入說明 + 附上 `IRL.json` 檔案
- STEP 3：每次開台流程提示（開 OBS → 開 NOALBS → `!start` → App 推流）
- 推流/拉流位址摘要 embed（`srtla://{ip}:5000?...`、`srt://{ip}:8282?...`、Moblin/IRL Pro 一鍵設定連結）
- NOALBS 聊天室指令說明（`!b`／`!ss`／`!r`／`!start`／`!stop`、Raid 自動停播說明）

**移除**（Vultr 專屬內容）：
- 伺服器規格、月費欄位
- Vultr API Key 顯示欄位
- 「未來如需刪除伺服器請用 `/irldelete`」提示

流程最後仍呼叫 `send_admin_log(user, "✅ 自架伺服器設定完成")` 記錄操作。

## 資料流

| 步驟 | 寫入 `state["data"]` |
|---|---|
| `handle_setup_mode` | `mode` |
| `handle_server_ip`（僅 self_hosted） | `server_ip` |
| `handle_twitch_id` | `twitch_id` |
| `handle_twitch_oauth` | `twitch_oauth` |
| `handle_obs_password` | `obs_password` |
| `handle_obs_port` | `obs_port` |

## on_message 分派表調整

`bot.py` 的 `handlers` dict 新增兩個 entry：

```python
"awaiting_setup_mode": handle_setup_mode,
"awaiting_server_ip":  handle_server_ip,
```

## 錯誤處理

延續現有專案風格：僅在使用者輸入的系統邊界做驗證（模式選擇需為 `1`/`2`；Twitch ID／OBS Port 沿用現有驗證），伺服器 IP 不驗證格式、不做連線測試（信任使用者輸入，屬非目標範圍）。`self_hosted` 完成流程若過程中發生例外（理論上僅檔案產生與 Discord 傳訊息可能失敗），比照現有風格記錄 log 並清除 `user_states`，不需額外重試機制。

## 影響檔案

- `bot.py`：新增 `handle_setup_mode`、`handle_server_ip`、`send_self_hosted_completion`；修改 `handle_disclaimer`（導向新的 `awaiting_setup_mode`）；修改 `handle_twitch_id`／`handle_twitch_oauth`／`handle_obs_password`／`handle_obs_port` 的 STEP 編號文字；修改 `handle_confirmation`（依 mode 分岔）；`on_message` 分派表新增兩個 entry
- `file_generator.py`：不修改
- `vultr_api.py`：不修改
- `README.md`：需補充新流程說明（後續實作階段一併更新）
