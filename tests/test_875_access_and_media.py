"""Regression coverage for protected adapter routes and native 875 media delivery."""
import base64
import xml.etree.ElementTree as ET

from aiohttp import web
from fastapi import FastAPI
import httpx
import pytest

from adapter.wechat_875.wx875client import WechatAPIClient
from adapter.wechat_875.wx875client import protocol875


@pytest.mark.parametrize(("source", "expected"), [
    ("<msgsource><atuserlist>bot,other</atuserlist></msgsource>", ["bot", "other"]),
    ({"string": "<msgsource><atuserlist><voipid><username>other</username></voipid></atuserlist></msgsource>"}, ["other"]),
    ("", []),
    ("<broken", []),
])
def test_mention_metadata_survives_normalization(source, expected):
    incoming = {"msgType": 1, "fromWxid": "room@chatroom", "content": "@bot", "msgSource": source}
    message = protocol875.normalize_875_message(incoming)
    node = ET.fromstring(message["msg_source"])
    members = (node.findtext("atuserlist") or "").split(",")
    assert [member for member in members if member] == expected


@pytest.mark.asyncio
async def test_guest_cannot_read_credentials_or_start_login(monkeypatch):
    from admin.routes import adapter_routes
    from admin.utils import auth_dependencies

    reads = []

    async def authenticate(request):
        return "fixture-user" if request.cookies.get("session") == "fixture-session" else None

    def config(name):
        reads.append(name)
        return {"accounts": [{"authcode": "fixture-only"}]}

    monkeypatch.setattr(auth_dependencies, "_check_auth_func", authenticate)
    monkeypatch.setattr(adapter_routes.adapter_manager, "get_adapter_config", config)
    app = FastAPI()
    app.include_router(adapter_routes.bp)
    base = "/api/adapters/wechat_875"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as browser:
        for method, url in (("GET", base), ("GET", base + "/login/status"), ("POST", base + "/login/start")):
            denied = await browser.request(method, url)
            assert denied.status_code == 401
            assert "fixture-only" not in denied.text
        assert reads == []
        browser.cookies.set("session", "fixture-session")
        allowed = await browser.get(base)
        assert allowed.status_code == 200
        assert allowed.json()["data"]["accounts"][0]["authcode"] == "fixture-only"


@pytest.mark.asyncio
async def test_native_file_and_video_send_once_with_their_original_contents(tmp_path):
    calls = []

    async def capture(request):
        calls.append((request.path, await request.json()))
        # 875 direct sends can also provide CDN metadata in the receipt.
        return web.json_response({"Success": True, "Code": 0, "Data": {
            "msgId": 817, "aesKey": "fixture-key", "cdnVideoUrl": "fixture-cdn",
        }})

    server = web.Application()
    server.router.add_post("/{path:.*}", capture)
    runner = web.AppRunner(server)
    await runner.setup()
    try:
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        client = WechatAPIClient("127.0.0.1", runner.addresses[0][1], protocol_version="875")
        client.set_active_auth_key("fixture")
        await client.send_video_message("test-peer", b"video", b"thumbnail", duration=3)
        attachment = tmp_path / "example.txt"
        attachment.write_bytes(b"attachment")
        receipt = await client.send_file_message("test-peer", attachment)

        assert [route for route, _ in calls] == ["/api/Msg/SendVideo", "/api/Msg/SendFile"]
        video, file = [body for _, body in calls]
        assert video["ToWxid"] == file["ToWxid"] == "test-peer"
        assert base64.b64decode(video["Base64"]) == b"video"
        assert base64.b64decode(video["ImageBase64"]) == b"thumbnail"
        assert video["PlayLength"] == 3
        assert base64.b64decode(file["Base64"]) == attachment.read_bytes()
        assert file["FileName"] == receipt["fileName"] == "example.txt"
        assert receipt["totalLen"] == len(attachment.read_bytes())
    finally:
        await runner.cleanup()
