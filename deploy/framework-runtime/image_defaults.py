"""Prepare an unconfigured framework image; mounted runtime data is supplied at launch."""
from pathlib import Path
import shutil

import tomlkit

app = Path("/app")
# Only the web and WeChat 875 adapters are used in this distribution.
for name in ("wechat_869", "wechat_875"):
    path = app / "adapter" / name / "config.toml"
    config = tomlkit.parse(path.read_text())
    config["adapter"]["enabled"] = name == "wechat_875"
    if name == "wechat_875":
        config["wechat875"].pop("accounts", None)
    path.write_text(tomlkit.dumps(config))

(app / "plugins/AssistantPlugin/config.toml").write_text("[Assistant]\nenable = false\n")
for relative in (
    "bot_status.json",
    "admin/bot_status.json",
    "resource/robot_stat.json",
    "WechatAPI/Client/login_stat.json",
    "plugins/AssistantPlugin/wx_session_pool.json",
):
    (app / relative).unlink(missing_ok=True)
accounts = app / "resource/accounts"
if accounts.exists():
    shutil.rmtree(accounts)
accounts.mkdir(parents=True)
for directory in ("database", "data"):
    (app / directory).mkdir(parents=True, exist_ok=True)
    for pattern in ("*.db", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3"):
        for database in (app / directory).glob(pattern):
            database.unlink()
