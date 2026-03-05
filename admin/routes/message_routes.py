"""
@input: FastAPI app、require_auth 鉴权依赖、bot_instance（可能为 XYBot 或 WechatAPIClient/Client869）
@output: 兼容旧前端的消息/群聊接口与 869 专属补齐接口（撤回/拍一拍/同步/二维码/标签/群信息/动态调用）
@position: 管理后台 routes 兼容层，避免旧页面 404 并为插件/调试提供 869 专属调用入口
@auto-doc: Update header and folder INDEX.md when this file changes
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from fastapi import Request, Depends
from fastapi.responses import JSONResponse
from loguru import logger


def register_message_routes(app) -> None:
    from admin.utils import require_auth
    from admin.core.app_setup import get_bot_instance

    def _resolve_client():
        bot = get_bot_instance()
        if bot is None:
            return None
        return getattr(bot, "bot", bot)

    def _is_client_869(client: Any) -> bool:
        if client is None:
            return False
        return str(getattr(client, "protocol_version", "") or "").lower() == "869"

    def _require_client_869(client: Any):
        if not _is_client_869(client):
            return {
                "success": False,
                "error": "当前不是 869 客户端，接口不可用",
                "require_protocol": "869",
                "current_protocol": str(getattr(client, "protocol_version", "") or ""),
            }
        return None

    async def _await_or_call(func: Any, *args: Any, **kwargs: Any):
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    @app.post("/api/send_message", response_class=JSONResponse, tags=["联系人"])
    async def api_send_message(request: Request, username: str = Depends(require_auth)):
        """发送文本消息到指定联系人（兼容旧前端）"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        to_wxid = payload.get("to_wxid")
        content = payload.get("content")
        at_users = payload.get("at", "")

        if not to_wxid or not content:
            return {"success": False, "error": "缺少必要参数，需要 to_wxid 与 content"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}

        send_func = getattr(target, "send_text_message", None)
        if not callable(send_func):
            return {"success": False, "error": "微信 API 不支持发送文本消息"}

        try:
            if inspect.iscoroutinefunction(send_func):
                result = await send_func(to_wxid, content, at_users)
            else:
                result = send_func(to_wxid, content, at_users)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return {"success": False, "error": f"发送消息失败: {str(e)}"}

        # 尽量兼容旧返回结构（不强依赖具体 SDK 返回值）
        data: Dict[str, Any] = {}
        if isinstance(result, (list, tuple)) and len(result) >= 3:
            data = {
                "client_msg_id": result[0],
                "create_time": result[1],
                "new_msg_id": result[2],
            }
        elif isinstance(result, dict):
            data = result

        return {"success": True, "message": "消息发送成功", "data": data}

    @app.post("/api/group/announcement", response_class=JSONResponse, tags=["联系人"])
    async def api_group_announcement(request: Request, username: str = Depends(require_auth)):
        """获取群公告（869 优先走真实接口，其他协议返回空公告）。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        wxid = payload.get("wxid")
        if not wxid:
            return {"success": False, "error": "缺少群聊ID(wxid)参数"}

        if not str(wxid).endswith("@chatroom"):
            return {"success": False, "error": "无效的群ID，只有群聊才有公告"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}

        # 仅 869 分支尝试调用真实接口
        if _is_client_869(target):
            get_announce = getattr(target, "get_chatroom_announce", None)
            if callable(get_announce):
                try:
                    raw = await get_announce(wxid) if inspect.iscoroutinefunction(get_announce) else get_announce(wxid)
                    announcement = ""
                    if isinstance(raw, dict):
                        for key in ("Announcement", "announcement", "ChatRoomAnnouncement", "chatroomAnnouncement", "Notice", "notice"):
                            value = raw.get(key)
                            if isinstance(value, str) and value.strip():
                                announcement = value.strip()
                                break
                    return {"success": True, "announcement": announcement, "raw": raw, "protocol": "869"}
                except Exception as e:
                    logger.warning(f"获取群公告失败(869): {e}")
                    return {"success": False, "error": f"获取群公告失败: {str(e)}", "protocol": "869"}

        # 非 869 分支维持兼容行为
        return {"success": True, "announcement": ""}

    @app.post("/api/869/message/revoke", response_class=JSONResponse, tags=["869专属"])
    async def api_869_revoke_message(request: Request, username: str = Depends(require_auth)):
        """869 专属：撤回消息。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        to_wxid = str(payload.get("to_wxid") or "").strip()
        client_msg_id = payload.get("client_msg_id")
        create_time = payload.get("create_time")
        new_msg_id = payload.get("new_msg_id")
        if not to_wxid or client_msg_id is None or create_time is None or new_msg_id is None:
            return {"success": False, "error": "缺少必要参数: to_wxid/client_msg_id/create_time/new_msg_id"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        revoke_func = getattr(target, "revoke_message", None)
        if not callable(revoke_func):
            return {"success": False, "error": "当前客户端不支持撤回接口"}
        try:
            ok = await revoke_func(to_wxid, int(client_msg_id), int(create_time), int(new_msg_id))
            return {"success": bool(ok), "data": {"ok": bool(ok)}}
        except Exception as e:
            logger.error(f"869 撤回消息失败: {e}")
            return {"success": False, "error": f"撤回失败: {str(e)}"}

    @app.post("/api/869/group/send_pat", response_class=JSONResponse, tags=["869专属"])
    async def api_869_send_pat(request: Request, username: str = Depends(require_auth)):
        """869 专属：群拍一拍。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        chatroom_wxid = str(payload.get("chatroom_wxid") or "").strip()
        to_wxid = str(payload.get("to_wxid") or "").strip()
        scene = int(payload.get("scene", 0) or 0)
        if not chatroom_wxid.endswith("@chatroom") or not to_wxid:
            return {"success": False, "error": "参数错误，需要有效的 chatroom_wxid 与 to_wxid"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        send_pat = getattr(target, "send_pat", None)
        if not callable(send_pat):
            return {"success": False, "error": "当前客户端不支持拍一拍接口"}
        try:
            data = await send_pat(chatroom_wxid, to_wxid, scene)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"869 群拍一拍失败: {e}")
            return {"success": False, "error": f"拍一拍失败: {str(e)}"}

    @app.post("/api/869/message/sync", response_class=JSONResponse, tags=["869专属"])
    async def api_869_sync_message(request: Request, username: str = Depends(require_auth)):
        """869 专属：HTTP 同步消息。"""
        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        sync_func = getattr(target, "sync_message", None)
        if not callable(sync_func):
            return {"success": False, "error": "当前客户端不支持同步消息接口"}
        try:
            ok, data = await sync_func()
            return {"success": bool(ok), "data": data}
        except Exception as e:
            logger.error(f"869 同步消息失败: {e}")
            return {"success": False, "error": f"同步失败: {str(e)}"}

    @app.post("/api/869/user/qrcode", response_class=JSONResponse, tags=["869专属"])
    async def api_869_user_qrcode(request: Request, username: str = Depends(require_auth)):
        """869 专属：获取个人二维码(base64)。"""
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        get_qrcode = getattr(target, "get_my_qrcode", None)
        if not callable(get_qrcode):
            return {"success": False, "error": "当前客户端不支持获取二维码接口"}

        style = int(payload.get("style", 0) or 0)
        try:
            qrcode = await _await_or_call(get_qrcode, style)
            return {"success": True, "data": {"base64": qrcode or ""}}
        except Exception as e:
            logger.error(f"869 获取个人二维码失败: {e}")
            return {"success": False, "error": f"获取二维码失败: {str(e)}"}

    @app.post("/api/869/label/list", response_class=JSONResponse, tags=["869专属"])
    async def api_869_label_list(request: Request, username: str = Depends(require_auth)):
        """869 专属：获取标签列表。"""
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        get_label_list = getattr(target, "get_label_list", None)
        if not callable(get_label_list):
            return {"success": False, "error": "当前客户端不支持标签接口"}

        wxid = str(payload.get("wxid") or "").strip() or None
        try:
            data = await _await_or_call(get_label_list, wxid)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"869 获取标签列表失败: {e}")
            return {"success": False, "error": f"获取标签失败: {str(e)}"}

    @app.post("/api/869/user/set_proxy", response_class=JSONResponse, tags=["869专属"])
    async def api_869_set_proxy(request: Request, username: str = Depends(require_auth)):
        """869 专属：设置代理（传 proxy 字符串或 proxy 对象）。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        set_proxy = getattr(target, "set_proxy", None)
        if not callable(set_proxy):
            return {"success": False, "error": "当前客户端不支持代理设置接口"}

        proxy_value = payload.get("proxy")
        if proxy_value is None:
            if isinstance(payload.get("proxy_config"), dict):
                proxy_value = payload.get("proxy_config")
            else:
                proxy_value = payload

        try:
            ok = await _await_or_call(set_proxy, proxy_value)
            return {"success": bool(ok), "data": {"ok": bool(ok)}}
        except Exception as e:
            logger.error(f"869 设置代理失败: {e}")
            return {"success": False, "error": f"设置代理失败: {str(e)}"}

    @app.post("/api/869/user/set_step", response_class=JSONResponse, tags=["869专属"])
    async def api_869_set_step(request: Request, username: str = Depends(require_auth)):
        """869 专属：修改步数。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        count = payload.get("count")
        if count is None:
            count = payload.get("step")
        if count is None:
            return {"success": False, "error": "缺少必要参数: count"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        set_step = getattr(target, "set_step", None)
        if not callable(set_step):
            return {"success": False, "error": "当前客户端不支持步数接口"}
        try:
            ok = await _await_or_call(set_step, int(count))
            return {"success": bool(ok), "data": {"ok": bool(ok)}}
        except Exception as e:
            logger.error(f"869 设置步数失败: {e}")
            return {"success": False, "error": f"设置步数失败: {str(e)}"}

    @app.post("/api/869/group/info", response_class=JSONResponse, tags=["869专属"])
    async def api_869_group_info(request: Request, username: str = Depends(require_auth)):
        """869 专属：获取群信息。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        chatroom = str(payload.get("chatroom") or payload.get("wxid") or "").strip()
        if not chatroom or not chatroom.endswith("@chatroom"):
            return {"success": False, "error": "缺少或无效群ID（chatroom/wxid）"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        get_group_info = getattr(target, "get_chatroom_info", None)
        if not callable(get_group_info):
            return {"success": False, "error": "当前客户端不支持群信息接口"}
        try:
            data = await _await_or_call(get_group_info, chatroom)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"869 获取群信息失败: {e}")
            return {"success": False, "error": f"获取群信息失败: {str(e)}"}

    @app.post("/api/869/group/qrcode", response_class=JSONResponse, tags=["869专属"])
    async def api_869_group_qrcode(request: Request, username: str = Depends(require_auth)):
        """869 专属：获取群二维码。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        chatroom = str(payload.get("chatroom") or payload.get("wxid") or "").strip()
        if not chatroom or not chatroom.endswith("@chatroom"):
            return {"success": False, "error": "缺少或无效群ID（chatroom/wxid）"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        get_group_qrcode = getattr(target, "get_chatroom_qrcode", None)
        if not callable(get_group_qrcode):
            return {"success": False, "error": "当前客户端不支持群二维码接口"}
        try:
            data = await _await_or_call(get_group_qrcode, chatroom)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"869 获取群二维码失败: {e}")
            return {"success": False, "error": f"获取群二维码失败: {str(e)}"}

    @app.post("/api/869/message/download_emoji", response_class=JSONResponse, tags=["869专属"])
    async def api_869_download_emoji(request: Request, username: str = Depends(require_auth)):
        """869 专属：下载表情（需传 msg_type=47 的 xml_content）。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        xml_content = str(payload.get("xml_content") or payload.get("xml") or payload.get("md5") or "").strip()
        if not xml_content:
            return {"success": False, "error": "缺少必要参数: xml_content"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        download_emoji = getattr(target, "download_emoji", None)
        if not callable(download_emoji):
            return {"success": False, "error": "当前客户端不支持表情下载接口"}
        try:
            data = await _await_or_call(download_emoji, xml_content)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"869 下载表情失败: {e}")
            return {"success": False, "error": f"下载表情失败: {str(e)}"}

    @app.post("/api/869/invoke", response_class=JSONResponse, tags=["869专属"])
    async def api_869_invoke(request: Request, username: str = Depends(require_auth)):
        """869 专属：动态调用 869 Swagger 路由。"""
        try:
            payload = await request.json()
        except Exception:
            return {"success": False, "error": "请求体不是合法 JSON"}

        target = _resolve_client()
        if target is None:
            return {"success": False, "error": "机器人实例未初始化，请确保机器人已启动"}
        protocol_check = _require_client_869(target)
        if protocol_check:
            return protocol_check

        body = payload.get("body")
        if body is not None and not isinstance(body, dict):
            return {"success": False, "error": "body 必须为对象(JSON object)"}
        params = payload.get("params")
        if params is not None and not isinstance(params, dict):
            return {"success": False, "error": "params 必须为对象(JSON object)"}

        method = str(payload.get("method") or "POST").upper()
        key = payload.get("key")
        path = str(payload.get("path") or "").strip()
        group = str(payload.get("group") or "").strip()
        action = str(payload.get("action") or "").strip()

        try:
            if path:
                call_path = getattr(target, "call_path", None)
                if not callable(call_path):
                    return {"success": False, "error": "当前客户端不支持 call_path"}
                data = await _await_or_call(call_path, path, body=body, method=method, key=key, params=params)
                return {"success": True, "data": data, "path": path, "method": method}

            if not group or not action:
                return {"success": False, "error": "缺少调用参数，请提供 path，或 group + action"}

            invoke = getattr(target, "invoke", None)
            if not callable(invoke):
                return {"success": False, "error": "当前客户端不支持 invoke"}
            data = await _await_or_call(invoke, group, action, body=body, method=method, key=key, params=params)
            return {"success": True, "data": data, "group": group, "action": action, "method": method}
        except Exception as e:
            logger.error(f"869 动态调用失败: {e}")
            return {"success": False, "error": f"动态调用失败: {str(e)}"}
