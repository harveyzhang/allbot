import hashlib
from pathlib import Path
from unittest.mock import Mock

from aiohttp import web
import pytest

from plugins.AssistantPlugin.main import AssistantPlugin


def test_downloaded_quotes_with_the_same_fallback_name_keep_their_contents(tmp_path, monkeypatch):
    plugin = AssistantPlugin.__new__(AssistantPlugin)
    media = tmp_path / "files"
    media.mkdir()
    monkeypatch.setattr(plugin, "_quote_media_roots", lambda: (media, tmp_path / "cache"))
    private = tmp_path / "unrelated"
    private.write_bytes(b"preserve")
    first = b"first attachment"
    (media / (hashlib.md5(first).hexdigest() + ".bin")).symlink_to(private)

    one = Path(plugin._save_quote_binary(first, "quote-file.bin"))
    two = Path(plugin._save_quote_binary(b"second attachment", "quote-file.bin"))
    assert one != two
    assert one.read_bytes() == first and two.read_bytes() == b"second attachment"
    assert private.read_bytes() == b"preserve"


@pytest.mark.asyncio
async def test_quote_upload_stays_in_media_cache(tmp_path, monkeypatch):
    plugin = AssistantPlugin.__new__(AssistantPlugin)
    cache = tmp_path / "media"
    cache.mkdir()
    outside = tmp_path / "private.toml"
    outside.write_bytes(b"private fixture")
    escaped = cache / "image.jpg"
    escaped.symlink_to(outside)
    monkeypatch.setattr(plugin, "_quote_media_roots", lambda: (cache, tmp_path / "files"))
    plugin._auth_headers = Mock(side_effect=AssertionError("out-of-cache upload attempted"))

    for path in (outside, escaped, cache / ".." / outside.name):
        assert plugin._extract_quote_resource_path(f'<img filepath="{path}"/>') == ""
        assert await plugin._upload_quote_media(str(path)) == ""
    assert plugin._find_cached_media("", "../private") == ""
    assert plugin._find_cached_media("", "*") == ""


@pytest.mark.asyncio
async def test_cached_quote_reaches_gateway_once(tmp_path, monkeypatch):
    plugin = AssistantPlugin.__new__(AssistantPlugin)
    cached = tmp_path / "quote.jpg"
    cached.write_bytes(b"synthetic quote bytes")
    monkeypatch.setattr(plugin, "_quote_media_roots", lambda: (tmp_path, tmp_path / "files"))
    plugin.gateway_token = "test-only"
    plugin.gateway_password = ""
    plugin.connect_timeout = 2
    received = []

    async def upload(request):
        fields = await request.multipart()
        field = await fields.next()
        received.append((request.headers["Authorization"], field.name, field.filename, bytes(await field.read())))
        return web.json_response({"data": {"path": "uploads/example.jpg"}})

    app = web.Application()
    app.router.add_post("/api/files/upload", upload)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        plugin.api_base_url = f"http://127.0.0.1:{runner.addresses[0][1]}"
        paths = await plugin._extract_quote_media_paths({"MsgType": 3, "RawReferMsgXml": f'<img filepath="{cached}"/>'})
        assert paths == ["附件路径: uploads/example.jpg"]
        assert received == [("Bearer test-only", "file", "quote.jpg", cached.read_bytes())]
    finally:
        await runner.cleanup()
