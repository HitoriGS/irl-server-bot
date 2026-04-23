import time
import logging
import paramiko

logger = logging.getLogger(__name__)

SETUP_COMMANDS = [
    (
        "📦 更新系統套件中（約 3-5 分鐘）...",
        "DEBIAN_FRONTEND=noninteractive apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
        600,
    ),
    (
        "🐳 啟動 belabox receiver 容器...",
        (
            "docker run -d --name belabox-receiver "
            "--log-opt max-size=50m --log-opt max-file=3 "
            "-p 5000:5000/udp -p 8181:8181/tcp -p 8282:8282/udp "
            "--restart=always --pull=always "
            "luminousaj/belabox-receiver:latest"
        ),
        300,
    ),
    (
        "⚙️ 設定 Docker 開機自動啟動...",
        "systemctl enable docker.service",
        30,
    ),
]


def generate_ssh_key():
    """產生 RSA 2048 金鑰對，回傳 (RSAKey物件, 公鑰字串)。"""
    key = paramiko.RSAKey.generate(2048)
    pub = f"ssh-rsa {key.get_base64()} irl-bot"
    return key, pub


def _connect(ip: str, private_key, max_attempts: int = 24, delay: int = 15) -> paramiko.SSHClient:
    """嘗試 SSH 連線，直到成功或超時。"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for attempt in range(1, max_attempts + 1):
        try:
            ssh.connect(ip, username="root", pkey=private_key, timeout=10, banner_timeout=30)
            logger.info(f"SSH connected to {ip} on attempt {attempt}")
            return ssh
        except Exception as e:
            logger.info(f"SSH attempt {attempt}/{max_attempts} failed: {e}")
            time.sleep(delay)
    raise ConnectionError(f"無法在 {max_attempts * delay} 秒內連線到 {ip}，請確認伺服器是否正常啟動。")


def _run(ssh: paramiko.SSHClient, command: str, timeout: int = 300):
    """執行指令並回傳 (exit_status, stdout, stderr)。"""
    _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    return exit_status, out, err


def setup_server_ssh(ip: str, private_key, progress_cb=None) -> bool:
    """
    SSH 進入伺服器，執行完整設定流程，最後重啟並驗證容器。
    progress_cb: 同步函式，接受字串訊息，用於回報進度。
    回傳 True 表示容器正常運行。
    """
    def notify(msg):
        if progress_cb:
            progress_cb(msg)

    # 第一次連線
    notify("🔗 正在等待伺服器 SSH 就緒（約 1-2 分鐘）...")
    ssh = _connect(ip, private_key)

    try:
        for label, cmd, timeout in SETUP_COMMANDS:
            notify(label)
            exit_status, out, err = _run(ssh, cmd, timeout=timeout)
            if exit_status != 0:
                logger.warning(f"Command exited {exit_status}: {err[:200]}")

        # 重啟伺服器
        notify("🔄 重啟伺服器中...")
        try:
            _run(ssh, "reboot", timeout=10)
        except Exception:
            pass
    finally:
        ssh.close()

    # 等待重啟完成
    time.sleep(40)

    # 重新連線，驗證容器狀態
    notify("🔍 重啟完成，驗證容器狀態...")
    ssh = _connect(ip, private_key, max_attempts=20, delay=15)
    try:
        _, out, _ = _run(ssh, "docker ps --format '{{.Names}}'", timeout=30)
        running = "belabox-receiver" in out
        if running:
            notify("✅ belabox-receiver 容器正常運行！")
        else:
            notify("⚠️ 容器未偵測到，可能仍在啟動中，請稍後手動確認。")
        return running
    finally:
        ssh.close()
