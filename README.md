# IRL Server Bot

一個 Discord 機器人，引導使用者一步步在 Vultr 上自動部署 IRL 直播伺服器，並產生 NOALBS 與 OBS 所需的設定檔。

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

## 部署

### 環境需求

- Python 3.11+
- Discord Bot Token
- 或直接使用 Docker

### 環境變數

| 變數 | 說明 |
|---|---|
| `DISCORD_TOKEN` | Discord Bot Token |

### 直接執行

```bash
pip install -r requirements.txt
DISCORD_TOKEN=your_token python bot.py
```

### Docker

```bash
docker build -t irl-server-bot .
docker run -e DISCORD_TOKEN=your_token irl-server-bot
```

## 檔案結構

```
irl-server-bot/
├── bot.py              # 主程式，Discord 事件與對話流程
├── file_generator.py   # 產生 config.json、.env、IRL.json
├── vultr_api.py        # Vultr API 操作（建立／查詢／刪除伺服器）
├── ssh_setup.py        # SSH 相關工具
├── requirements.txt
└── Dockerfile
```

## 注意事項

- 使用者提供的所有資訊（API Key、OAuth Token、OBS 密碼）**僅存在於 Discord 私訊記憶體中**，不會寫入任何資料庫或檔案
- 建立 Vultr API Key 時，Access Control List 請保持空白
