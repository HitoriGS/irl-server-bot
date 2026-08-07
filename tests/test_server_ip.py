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


@pytest.mark.asyncio
async def test_handle_server_ip_cancel_clears_state(fake_message, fake_user):
    bot_module.user_states[fake_user.id] = {
        "step": "awaiting_server_ip", "data": {"mode": "self_hosted"}
    }
    msg = fake_message("取消")
    await bot_module.handle_server_ip(msg, bot_module.user_states[fake_user.id])
    assert fake_user.id not in bot_module.user_states
    assert "已取消" in msg.channel.sent[-1]["content"]
