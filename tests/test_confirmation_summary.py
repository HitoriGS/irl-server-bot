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
