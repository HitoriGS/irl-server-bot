import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_confirmation_self_hosted_generates_files_and_clears_state(fake_user, fake_message):
    bot_module.user_states[fake_user.id] = {
        "step": "confirming",
        "data": {
            "mode": "self_hosted",
            "server_ip": "203.0.113.10",
            "twitch_id": "hitorigs",
            "twitch_oauth": "abcdefgh12345",
            "obs_password": "secretpw",
            "obs_port": 4455,
        },
    }
    state = bot_module.user_states[fake_user.id]
    msg = fake_message("確認")
    await bot_module.handle_confirmation(msg, state)

    assert fake_user.id not in bot_module.user_states
    sent = fake_user.channel.sent
    filenames = [f.filename for item in sent if item.get("files") for f in item["files"]]
    assert "config.json" in filenames
    assert ".env" in filenames
    assert "IRL.json" in filenames


@pytest.mark.asyncio
async def test_send_self_hosted_completion_content(fake_user):
    state = {
        "data": {
            "server_ip": "203.0.113.10",
            "twitch_id": "hitorigs",
            "twitch_oauth": "abcdefgh12345",
            "obs_password": "secretpw",
            "obs_port": 4455,
        }
    }
    await bot_module.send_self_hosted_completion(fake_user, state)
    embeds = [item["embed"] for item in fake_user.channel.sent if item.get("embed")]
    titles = [e.title for e in embeds if e.title]
    assert any("安裝 NOALBS" in t for t in titles)
    assert any("OBS 場景集" in t for t in titles)
    assert not any("伺服器規格" in (f.name or "") for e in embeds for f in e.fields)
