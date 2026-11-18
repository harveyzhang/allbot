"""Quoted content must never become a current command; cached originals expire."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest

from adapter.wechat_875.adapter import Wechat875Adapter, w875_cache_get_raw, w875_cache_set


@pytest.mark.parametrize(("title", "xml_title", "expected"), [
    ("new request", "fallback", "new request"),
    ("", "new fallback", "new fallback"),
    ("", "", ""),
])
def test_quoted_old_command_never_replaces_current_title(title, xml_title, expected):
    adapter = Wechat875Adapter.__new__(Wechat875Adapter)
    adapter.skip_self_message = True
    adapter.platform = "fixture"
    adapter.adapter_name = "wechat_875"
    adapter._cache_prefix = "fixture:raw:"
    adapter._redis = None
    adapter._logger = Mock()
    account = SimpleNamespace(wxid="bot", client=SimpleNamespace(wxid="bot"))
    raw = {"msgType": 49, "fromWxid": "peer", "toWxid": "bot", "msgId": 42,
           "content": "old dangerous command", "xml_fields": {"title": xml_title},
           "app": {"title": title, "reference": {"msg_type": 1, "svr_id": "original", "content": "old dangerous command"}}}
    result = adapter._normalize_to_standard(account, raw)
    xml = ET.fromstring(result["Content"]["string"])
    assert (xml.findtext("appmsg/title") or "").strip() == expected
    assert xml.findtext("appmsg/refermsg/content") == "old dangerous command"
    assert result["ChannelId"] == "peer" and result["account_wxid"] == "bot"


def test_raw_cache_has_expiry_and_tolerates_bad_values():
    redis = Mock()
    pipe = redis.pipeline.return_value
    raw = {"new_msg_id": "a", "svr_id": "b", "id": "c", "kind": "text", "content": "original"}
    w875_cache_set(redis, "fixture:raw:", 604800, raw)
    assert [call.args[:2] for call in pipe.setex.call_args_list] == [
        ("fixture:raw:a", 604800), ("fixture:raw:b", 604800), ("fixture:raw:c", 604800)]
    pipe.execute.assert_called_once()
    redis.get.return_value = json.dumps(raw).encode()
    assert w875_cache_get_raw(redis, "fixture:raw:", "b") == raw
    redis.get.assert_called_once_with("fixture:raw:b")
    for malformed in (None, b"broken", b"[]"):
        redis.get.return_value = malformed
        assert w875_cache_get_raw(redis, "fixture:raw:", "b") == {}
