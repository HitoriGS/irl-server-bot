import requests
import time
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.vultr.com/v2"
PLAN = "vhp-1c-1gb-intel"


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

    # ── Marketplace App ────────────────────────────────────────────────────
    def get_docker_app_id(self):
        """查詢 Vultr 上的 Docker App ID，依序嘗試不同 type 參數。"""
        type_filters = [None, "one-click", "marketplace"]
        for type_filter in type_filters:
            try:
                params = {"per_page": 500}
                if type_filter:
                    params["type"] = type_filter
                resp = self._get("/applications", params=params)
                if resp.status_code != 200:
                    continue
                apps = resp.json().get("applications", [])
                logger.info(f"[type={type_filter}] {len(apps)} apps: "
                            + str([a.get("short_name") for a in apps[:20]]))
                for app in apps:
                    short = app.get("short_name", "").lower()
                    name  = app.get("name", "").lower()
                    if "docker" in short or "docker" in name:
                        logger.info(f"Docker matched: id={app['id']} short={short}")
                        return app["id"]
            except Exception as e:
                logger.error(f"get_docker_app_id error (type={type_filter}): {e}")
        logger.error("Docker app not found in any type filter.")
        return None

    # ── SSH Key ────────────────────────────────────────────────────────────
    def add_ssh_key(self, name: str, public_key: str) -> str:
        resp = self._post("/ssh-keys", {"name": name, "ssh_key": public_key})
        resp.raise_for_status()
        key_id = resp.json()["ssh_key"]["id"]
        logger.info(f"SSH key uploaded: {key_id}")
        return key_id

    def delete_ssh_key(self, ssh_key_id: str):
        try:
            self._delete(f"/ssh-keys/{ssh_key_id}")
        except Exception as e:
            logger.warning(f"delete_ssh_key failed: {e}")

    # ── Instance ───────────────────────────────────────────────────────────
    def create_instance(self, region: str, ssh_key_id: str, app_id: int) -> dict:
        payload = {
            "region": region,
            "plan": PLAN,
            "app_id": app_id,
            "sshkey_id": [ssh_key_id],
            "backups": "disabled",
            "label": "irl-server",
            "hostname": "irl-server",
        }
        resp = self._post("/instances", payload)
        resp.raise_for_status()
        instance = resp.json()["instance"]
        logger.info(f"Instance created: {instance['id']}")
        return instance

    def get_instance(self, instance_id: str) -> dict:
        resp = self._get(f"/instances/{instance_id}")
        resp.raise_for_status()
        return resp.json()["instance"]

    def wait_for_active(self, instance_id: str, timeout: int = 360) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            instance = self.get_instance(instance_id)
            status = instance.get("status")
            ip = instance.get("main_ip", "0.0.0.0")
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
