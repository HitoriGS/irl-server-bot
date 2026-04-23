import json
import copy

# ── NOALBS config.json 模板 ───────────────────────────────────────────────────
CONFIG_TEMPLATE = {
    "user": {"id": None, "name": "{{TWITCH_ID}}", "passwordHash": None},
    "switcher": {
        "bitrateSwitcherEnabled": True,
        "onlySwitchWhenStreaming": True,
        "instantlySwitchOnRecover": True,
        "autoSwitchNotification": True,
        "retryAttempts": 5,
        "triggers": {"low": 800, "rtt": 1500, "offline": 300},
        "switchingScenes": {"normal": "LIVE", "low": "LOW", "offline": "BRB"},
        "streamServers": [
            {
                "streamServer": {
                    "type": "Belabox",
                    "statsUrl": "http://use.srt.belabox.net:8080/XXXXXXXXXX(STREAMID)XXXXXXXXXX",
                    "publisher": "XXXXXXXXXX(STREAMID)XXXXXXXXXX",
                },
                "name": "BELABOX cloud",
                "priority": 0,
                "overrideScenes": None,
                "dependsOn": None,
                "enabled": False,
            },
            {
                "streamServer": {
                    "type": "SrtLiveServer",
                    "statsUrl": "http://{{SERVER_IP}}:8181/stats",
                    "publisher": "live/stream/belabox",
                },
                "name": "SRT",
                "priority": 0,
                "overrideScenes": None,
                "dependsOn": None,
                "enabled": True,
            },
            {
                "streamServer": {
                    "type": "Nginx",
                    "statsUrl": "http://localhost/stats",
                    "application": "live",
                    "key": "rtmp1",
                },
                "name": "nginx",
                "priority": 1,
                "overrideScenes": None,
                "dependsOn": None,
                "enabled": False,
            },
        ],
    },
    "software": {
        "type": "Obs",
        "host": "localhost",
        "password": "{{OBS_PASSWORD}}",
        "port": 4455,
        "collections": {
            "twitch": {"profile": "Twitch", "collection": "IRL"},
            "kick": {"profile": "kick", "collection": "kick_scenes"},
        },
    },
    "chat": {
        "platform": "Twitch",
        "username": "{{TWITCH_ID}}",
        "admins": ["{{TWITCH_ID}}"],
        "language": "ZHTW",
        "prefix": "!",
        "enablePublicCommands": True,
        "enableModCommands": True,
        "enableAutoStopStreamOnHostOrRaid": True,
        "announceRaidOnAutoStop": True,
        "commands": {
            "Fix":     {"permission": "Mod",   "userPermissions": None, "alias": ["f"]},
            "Switch":  {"permission": "Admin",  "userPermissions": None, "alias": ["ss"]},
            "Bitrate": {"permission": None,     "userPermissions": None, "alias": ["b"]},
            "Refresh": {"permission": "Mod",   "userPermissions": None, "alias": ["r"]},
        },
    },
    "optionalScenes": {
        "starting": "STARTING",
        "ending": "ENDING",
        "privacy": "PRIVACY",
        "refresh": "BRB",
    },
    "optionalOptions": {
        "twitchTranscodingCheck": False,
        "twitchTranscodingRetries": 5,
        "twitchTranscodingDelaySeconds": 15,
        "offlineTimeout": None,
        "recordWhileStreaming": False,
        "switchToStartingSceneOnStreamStart": False,
        "switchFromStartingSceneToLiveScene": False,
    },
}

# ── OBS 場景集 IRL.json 模板 ──────────────────────────────────────────────────
OBS_TEMPLATE = {
    "current_scene": "LIVE",
    "current_program_scene": "LIVE",
    "scene_order": [{"name": "LIVE"}, {"name": "LOW"}, {"name": "BRB"}],
    "name": "IRL",
    "groups": [],
    "quick_transitions": [
        {"name": "直接轉場", "duration": 300, "hotkeys": [], "id": 1, "fade_to_black": False},
        {"name": "淡入淡出", "duration": 300, "hotkeys": [], "id": 2, "fade_to_black": False},
        {"name": "淡入淡出", "duration": 300, "hotkeys": [], "id": 3, "fade_to_black": True},
    ],
    "transitions": [],
    "saved_projectors": [],
    "current_transition": "淡入淡出",
    "transition_duration": 300,
    "preview_locked": False,
    "scaling_enabled": True,
    "scaling_level": 0,
    "scaling_off_x": 0.0,
    "scaling_off_y": 0.0,
    "virtual-camera": {"type2": 3},
    "modules": {
        "scripts-tool": [],
        "output-timer": {
            "streamTimerHours": 0, "streamTimerMinutes": 0, "streamTimerSeconds": 30,
            "recordTimerHours": 0, "recordTimerMinutes": 0, "recordTimerSeconds": 30,
            "autoStartStreamTimer": False, "autoStartRecordTimer": False, "pauseRecordTimer": False,
        },
        "auto-scene-switcher": {
            "interval": 300, "non_matching_scene": "",
            "switch_if_not_matching": False, "active": False, "switches": [],
        },
    },
    "resolution": {"x": 1920, "y": 1080},
    "version": 2,
    "sources": [
        {
            "prev_ver": 520093699,
            "name": "媒體來源",
            "uuid": "d3f8fc75-841d-4c4c-bb8d-e5a81bd11972",
            "id": "ffmpeg_source",
            "versioned_id": "ffmpeg_source",
            "settings": {
                "input": "srt://{{SERVER_IP}}:8282?streamid=play/stream/belabox",
                "input_format": "",
                "is_local_file": False,
                "reconnect_delay_sec": 5,
            },
            "mixers": 255, "sync": 0, "flags": 0,
            "volume": 1.0, "balance": 0.5, "enabled": True,
            "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
            "push-to-talk": False, "push-to-talk-delay": 0,
            "hotkeys": {
                "libobs.mute": [], "libobs.unmute": [],
                "libobs.push-to-mute": [], "libobs.push-to-talk": [],
                "MediaSource.Restart": [], "MediaSource.Play": [],
                "MediaSource.Pause": [], "MediaSource.Stop": [],
            },
            "deinterlace_mode": 0, "deinterlace_field_order": 0,
            "monitoring_type": 0, "private_settings": {},
        },
        {
            "prev_ver": 520093699,
            "name": "BRB提示",
            "uuid": "2ab848c8-ce91-4e9b-9dde-76840d7ea4bb",
            "id": "text_ft2_source",
            "versioned_id": "text_ft2_source_v2",
            "settings": {
                "font": {"face": "Noto Sans CJK TC", "style": "Regular", "size": 96, "flags": 0},
                "text": "【斷線場景】\n這邊可放個人靜態圖/剪輯影片/文字內容等\n讓觀眾稍候不要轉台",
            },
            "mixers": 0, "sync": 0, "flags": 0,
            "volume": 1.0, "balance": 0.5, "enabled": True,
            "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
            "push-to-talk": False, "push-to-talk-delay": 0,
            "hotkeys": {},
            "deinterlace_mode": 0, "deinterlace_field_order": 0,
            "monitoring_type": 0, "private_settings": {},
        },
        {
            "prev_ver": 520093699,
            "name": "BRB",
            "uuid": "2545263d-ece4-4c0e-8173-68f472d034b7",
            "id": "scene",
            "versioned_id": "scene",
            "settings": {
                "id_counter": 3,
                "custom_size": False,
                "items": [
                    {
                        "name": "BRB提示",
                        "source_uuid": "2ab848c8-ce91-4e9b-9dde-76840d7ea4bb",
                        "visible": True, "locked": False, "rot": 0.0,
                        "scale_ref": {"x": 1920.0, "y": 1080.0},
                        "align": 5, "bounds_type": 0, "bounds_align": 0, "bounds_crop": False,
                        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
                        "id": 3, "group_item_backup": False,
                        "pos": {"x": 364.0, "y": 427.0},
                        "pos_rel": {"x": -1.1037037372589111, "y": -0.2092592716217041},
                        "scale": {"x": 0.66075390577316284, "y": 0.66081869602203369},
                        "scale_rel": {"x": 0.66075390577316284, "y": 0.66081869602203369},
                        "bounds": {"x": 0.0, "y": 0.0},
                        "bounds_rel": {"x": 0.0, "y": 0.0},
                        "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
                        "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
                        "private_settings": {},
                    }
                ],
            },
            "mixers": 0, "sync": 0, "flags": 0,
            "volume": 1.0, "balance": 0.5, "enabled": True,
            "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
            "push-to-talk": False, "push-to-talk-delay": 0,
            "hotkeys": {
                "OBSBasic.SelectScene": [],
                "libobs.show_scene_item.3": [], "libobs.hide_scene_item.3": [],
            },
            "deinterlace_mode": 0, "deinterlace_field_order": 0,
            "monitoring_type": 0, "private_settings": {},
        },
        {
            "prev_ver": 520093699,
            "name": "LIVE",
            "uuid": "3843cf59-590a-48af-b5cd-335eecf9f9c1",
            "id": "scene",
            "versioned_id": "scene",
            "settings": {
                "id_counter": 2,
                "custom_size": False,
                "items": [
                    {
                        "name": "媒體來源",
                        "source_uuid": "d3f8fc75-841d-4c4c-bb8d-e5a81bd11972",
                        "visible": True, "locked": False, "rot": 0.0,
                        "scale_ref": {"x": 1920.0, "y": 1080.0},
                        "align": 5, "bounds_type": 2, "bounds_align": 0, "bounds_crop": False,
                        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
                        "id": 2, "group_item_backup": False,
                        "pos": {"x": 0.0, "y": 0.0},
                        "pos_rel": {"x": -1.7777777910232544, "y": -1.0},
                        "scale": {"x": 1.0, "y": 1.0},
                        "scale_rel": {"x": 1.0, "y": 1.0},
                        "bounds": {"x": 1920.0, "y": 1080.0},
                        "bounds_rel": {"x": 3.5555555820465088, "y": 2.0},
                        "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
                        "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
                        "private_settings": {},
                    }
                ],
            },
            "mixers": 0, "sync": 0, "flags": 0,
            "volume": 1.0, "balance": 0.5, "enabled": True,
            "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
            "push-to-talk": False, "push-to-talk-delay": 0,
            "hotkeys": {
                "OBSBasic.SelectScene": [],
                "libobs.show_scene_item.2": [], "libobs.hide_scene_item.2": [],
            },
            "deinterlace_mode": 0, "deinterlace_field_order": 0,
            "monitoring_type": 0, "private_settings": {},
        },
        {
            "prev_ver": 520093699,
            "name": "LOW",
            "uuid": "63bcaf8e-8e0b-452e-9af8-c5323423f26f",
            "id": "scene",
            "versioned_id": "scene",
            "settings": {
                "id_counter": 2,
                "custom_size": False,
                "items": [
                    {
                        "name": "媒體來源",
                        "source_uuid": "d3f8fc75-841d-4c4c-bb8d-e5a81bd11972",
                        "visible": True, "locked": False, "rot": 0.0,
                        "scale_ref": {"x": 1920.0, "y": 1080.0},
                        "align": 5, "bounds_type": 0, "bounds_align": 0, "bounds_crop": False,
                        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
                        "id": 1, "group_item_backup": False,
                        "pos": {"x": 0.0, "y": 0.0},
                        "pos_rel": {"x": -1.7777777910232544, "y": -1.0},
                        "scale": {"x": 1.0, "y": 1.0},
                        "scale_rel": {"x": 1.0, "y": 1.0},
                        "bounds": {"x": 0.0, "y": 0.0},
                        "bounds_rel": {"x": 0.0, "y": 0.0},
                        "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
                        "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
                        "private_settings": {},
                    },
                    {
                        "name": "LowBitrate",
                        "source_uuid": "f8b91bd2-c984-4300-bc94-7815744dc7df",
                        "visible": True, "locked": False, "rot": 0.0,
                        "scale_ref": {"x": 1920.0, "y": 1080.0},
                        "align": 5, "bounds_type": 0, "bounds_align": 0, "bounds_crop": False,
                        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
                        "id": 2, "group_item_backup": False,
                        "pos": {"x": 191.0, "y": 0.0},
                        "pos_rel": {"x": -1.4240740537643433, "y": -1.0},
                        "scale": {"x": 0.71203702688217163, "y": 0.7118644118309021},
                        "scale_rel": {"x": 0.71203702688217163, "y": 0.7118644118309021},
                        "bounds": {"x": 0.0, "y": 0.0},
                        "bounds_rel": {"x": 0.0, "y": 0.0},
                        "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
                        "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
                        "private_settings": {},
                    },
                ],
            },
            "mixers": 0, "sync": 0, "flags": 0,
            "volume": 1.0, "balance": 0.5, "enabled": True,
            "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
            "push-to-talk": False, "push-to-talk-delay": 0,
            "hotkeys": {
                "OBSBasic.SelectScene": [],
                "libobs.show_scene_item.1": [], "libobs.hide_scene_item.1": [],
                "libobs.show_scene_item.2": [], "libobs.hide_scene_item.2": [],
            },
            "deinterlace_mode": 0, "deinterlace_field_order": 0,
            "monitoring_type": 0, "private_settings": {},
        },
        {
            "prev_ver": 520093699,
            "name": "LowBitrate",
            "uuid": "f8b91bd2-c984-4300-bc94-7815744dc7df",
            "id": "text_ft2_source",
            "versioned_id": "text_ft2_source_v2",
            "settings": {
                "font": {"face": "Noto Sans Mono CJK TC", "style": "Regular", "size": 96, "flags": 0},
                "text": "訊號不良...請稍候（可自行修改文字內容及位置）",
            },
            "mixers": 0, "sync": 0, "flags": 0,
            "volume": 1.0, "balance": 0.5, "enabled": True,
            "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
            "push-to-talk": False, "push-to-talk-delay": 0,
            "hotkeys": {},
            "deinterlace_mode": 0, "deinterlace_field_order": 0,
            "monitoring_type": 0, "private_settings": {},
        },
    ],
}


# ── 產生函式 ──────────────────────────────────────────────────────────────────

def generate_config_json(twitch_id: str, server_ip: str, obs_password: str) -> str:
    cfg = copy.deepcopy(CONFIG_TEMPLATE)
    cfg["user"]["name"] = twitch_id
    cfg["switcher"]["streamServers"][1]["streamServer"]["statsUrl"] = f"http://{server_ip}:8181/stats"
    cfg["software"]["password"] = obs_password
    cfg["chat"]["username"] = twitch_id
    cfg["chat"]["admins"] = [twitch_id]
    return json.dumps(cfg, ensure_ascii=False, indent=2)


def generate_env_file(twitch_id: str, oauth_token: str) -> str:
    if not oauth_token.lower().startswith("oauth:"):
        oauth_token = f"oauth:{oauth_token}"
    return f"TWITCH_BOT_USERNAME={twitch_id}\nTWITCH_BOT_OAUTH={oauth_token}\n"


def generate_obs_json(server_ip: str) -> str:
    obs = copy.deepcopy(OBS_TEMPLATE)
    for source in obs["sources"]:
        if source.get("id") == "ffmpeg_source":
            source["settings"]["input"] = f"srt://{server_ip}:8282?streamid=play/stream/belabox"
    return json.dumps(obs, ensure_ascii=False, indent=4)
