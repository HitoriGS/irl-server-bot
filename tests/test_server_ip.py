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
