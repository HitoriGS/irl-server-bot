import requests
import time
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.vultr.com/v2"
PLAN     = "vhp-1c-1gb-intel"

STARTUP_SCRIPT = """#!/bin/bash
set -e
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
apt-get install -y docker.io
systemctl enable docker
systemctl start docker
docker run -d --name belabox-receiver \
  --log-opt max-size=50m \
  --log-opt max-file=3 \
  -p 5000:5000/udp \
  -p 8181:8181/tcp \
  -p 8282:8282/udp \
  --restart=always \
  --pull=always \
  luminousaj/belabox-receiver:latest
"""


class VultrAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _get(self, path, params=None):
        return requests.get(f"{BASE_URL}{path}", headers=self.headers, params=params, timeout=15)

    def _post(self, path, json):
        return requests.post(f"{BASE_URL}{path}", headers=self.headers, json=json, timeout=15)

    def _delete(self, path):
        return requests.delete(f"{BASE_URL}{path}", headers=self.headers, timeout=15)

    # ── 驗證 ──────────────────────────────────────────────────────────────
    def validate_key(self) -> bool:
        try:
            resp = self._get("/account")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"validate_key error: {e}")
            return False

    # ── OS ─────────────────────────────────────────────────────────────────
    def get_ubuntu_os_id(self) -> int:
        """取得 Ubuntu 22.04 LTS 的 OS ID。"""
        resp = self._get("/os", params={"per_page": 500})
        resp.raise_for_status()
        for os in resp.json().get("os", []):
            name = os.get("name", "")
            if "Ubuntu" in name and "22.04" in name and "LTS" in name and "x64" in name:
                logger.info(f"Ubuntu OS found: id={os['id']} name={name}")
                return os["id"]
        raise RuntimeError("找不到 Ubuntu 22.04 LTS x64，請聯繫管理員。")

    # ── Startup Script ─────────────────────────────────────────────────────
    def create_startup_script(self, name: str) -> str:
        """建立 Startup Script，回傳 script ID。"""
        resp = self._post("/startup-scripts", {
            "name": name,
            "type": "boot",
            "script": STARTUP_SCRIPT,
        })
        resp.raise_for_status()
        script_id = resp.json()["startup_script"]["id"]
        logger.info(f"Startup script created: {script_id}")
        return script_id

    def delete_startup_script(self, script_id: str):
        try:
            self._delete(f"/startup-scripts/{script_id}")
            logger.info(f"Startup script deleted: {script_id}")
        except Exception as e:
            logger.warning(f"delete_startup_script failed: {e}")

    # ── Instance ───────────────────────────────────────────────────────────
    def create_instance(self, region: str, os_id: int, script_id: str) -> dict:
        payload = {
            "region":    region,
            "plan":      PLAN,
            "os_id":     os_id,
            "script_id": script_id,
            "backups":   "disabled",
            "label":     "irl-server",
            "hostname":  "irl-server",
        }
        logger.info(f"Creating instance: {payload}")
        resp = self._post("/instances", payload)
        if not resp.ok:
            logger.error(f"Create instance failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()
        instance = resp.json()["instance"]
        logger.info(f"Instance created: {instance['id']}")
        return instance

    def get_instance(self, instance_id: str) -> dict:
        resp = self._get(f"/instances/{instance_id}")
        resp.raise_for_status()
        return resp.json()["instance"]

    def wait_for_active(self, instance_id: str, timeout: int = 360) -> str:
        """等待 VPS 啟動完成並回傳 IP。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            instance = self.get_instance(instance_id)
            status = instance.get("status")
            ip     = instance.get("main_ip", "0.0.0.0")
            logger.info(f"Instance {instance_id}: status={status} ip={ip}")
            if status == "active" and ip and ip != "0.0.0.0":
                return ip
            time.sleep(10)
        raise TimeoutError("伺服器在時限內未完成啟動，請到 Vultr 後台確認。")

    def delete_instance(self, instance_id: str):
        try:
            self._delete(f"/instances/{instance_id}")
            logger.info(f"Instance deleted: {instance_id}")
        except Exception as e:
            logger.warning(f"delete_instance failed: {e}")
