import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_self_hosted_full_flow_via_step_handlers(fake_message, fake_user):
    """透過 STEP_HANDLERS 分派表，完整走一次自架伺服器對話流程：
    disclaimer → setup_mode → server_ip → twitch_id → twitch_oauth →
    obs_password → obs_port → confirming → completion。
    """
    state = {"step": "awaiting_disclaimer", "data": {}}
    bot_module.user_states[fake_user.id] = state

    inputs = [
        "同意",              # disclaimer
        "2",                 # setup_mode -> 已有自己的伺服器
        "203.0.113.10",      # server_ip
        "hitorigs",          # twitch_id
        "abc123oauthtoken",  # twitch_oauth
        "secretpw",          # obs_password
        "4455",              # obs_port
        "確認",              # confirming -> 觸發 send_self_hosted_completion
    ]

    for text in inputs:
        handler = bot_module.STEP_HANDLERS[state["step"]]
        msg = fake_message(text)
        await handler(msg, state)

    assert fake_user.id not in bot_module.user_states
    assert state["data"]["mode"] == "self_hosted"
    assert state["data"]["server_ip"] == "203.0.113.10"
    assert state["data"]["twitch_id"] == "hitorigs"
    assert state["data"]["obs_port"] == 4455

    sent_files = [m["files"] for m in fake_user.channel.sent if m["files"]]
    assert sent_files, "完成流程應附上 config.json 與 .env 檔案"
    filenames = {f.filename for batch in sent_files for f in batch}
    assert {"config.json", ".env"} <= filenames
