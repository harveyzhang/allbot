"""Render the two protocol config files without expanding credentials into commands or logs."""
import os
from pathlib import Path
import re
import sys


def patch_entrypoint():
    path = Path("/app/entrypoint.sh")
    original = path.read_text()
    start = original.index("WX_TOKEN_KEY_EFFECTIVE=")
    end = original.index('\nif [ -x "$APP_DIR/pad-face-verify-linux-x64" ]; then', start)
    replace = 'python3 /opt/protocol-runtime/configure.py "$CONF_DST" "$APP_DIR/conf/app.conf"\n'
    path.write_text(original[:start] + replace + original[end:])


def configure(files):
    token_file = os.environ.get("WX_TOKEN_KEY_FILE")
    if token_file:
        token = Path(token_file).read_text().rstrip("\r\n")
        if not token:
            raise ValueError("empty protocol credential file")
    else:
        token = os.environ.get("WX_TOKEN_KEY") or "local-dev-placeholder"
    redis_link = os.environ.get("WX_REDIS_LINK")
    if any(c in token for c in ('\r', '\n', '"')) or any(c in (redis_link or '') for c in ('\r', '\n')):
        raise ValueError("protocol settings must each fit a single config line")
    settings = {"user_token_key": f'"{token}"'}
    if redis_link:
        settings["redislink"] = redis_link
    for path in map(Path, files):
        text = path.read_text()
        for field, value in settings.items():
            text, count = re.subn(rf"(?m)^{field}\s*=[^\r\n]*", lambda _: f"{field} = {value}", text)
            if count != 1:
                raise ValueError(f"expected exactly one {field} setting")
        path.chmod(0o600)
        path.write_text(text)
    print("[entrypoint] 875 授权配置已加载")


if __name__ == "__main__":
    if sys.argv[1:] == ["--patch-entrypoint"]:
        patch_entrypoint()
    else:
        configure(sys.argv[1:])
