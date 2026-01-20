"""
提醒管理路由模块

职责：处理用户提醒的 CRUD 操作
"""
import os
import json
from fastapi import Request, Depends
from fastapi.responses import JSONResponse
from loguru import logger


def register_reminder_routes(app):
    """
    注册提醒管理相关路由

    Args:
        app: FastAPI 应用实例
    """
    from admin.utils import require_auth

    current_dir = os.path.dirname(os.path.abspath(__file__))

    def get_reminder_file_path(wxid: str) -> str:
        """获取用户提醒数据文件路径"""
        reminders_dir = os.path.join(current_dir, "reminders")
        if not os.path.exists(reminders_dir):
            os.makedirs(reminders_dir, exist_ok=True)
        return os.path.join(reminders_dir, f"{wxid}_reminders.json")

    @app.get("/api/reminders/{wxid}", response_class=JSONResponse)
    async def api_get_reminders(wxid: str, request: Request, username: str = Depends(require_auth)):
        """获取用户的提醒列表"""
        try:
            logger.info(f"用户 {username} 请求获取 {wxid} 的提醒列表")

            reminders_file = get_reminder_file_path(wxid)
            logger.info(f"尝试从 {reminders_file} 加载提醒数据")

            if not os.path.exists(reminders_file):
                logger.warning(f"提醒文件不存在: {reminders_file}")
                return JSONResponse(content={"success": True, "reminders": []})

            with open(reminders_file, "r", encoding="utf-8") as f:
                try:
                    reminders = json.load(f)
                    logger.info(f"从文件成功加载提醒，条目数: {len(reminders)}")
                    return JSONResponse(content={"success": True, "reminders": reminders})
                except json.JSONDecodeError as e:
                    logger.error(f"解析 {wxid} 的提醒文件失败: {str(e)}")
                    return JSONResponse(content={"success": False, "error": f"解析提醒数据失败: {str(e)}"})

        except Exception as e:
            logger.exception(f"获取用户 {wxid} 的提醒列表失败: {str(e)}")
            return JSONResponse(content={"success": False, "error": f"获取提醒列表失败: {str(e)}"})

    @app.get("/api/reminders/{wxid}/{id}", response_class=JSONResponse)
    async def api_get_reminder(wxid: str, id: int, request: Request, username: str = Depends(require_auth)):
        """获取特定提醒详情"""
        try:
            logger.info(f"用户 {username} 请求获取 {wxid} 的提醒 {id} 详情")

            reminders_file = get_reminder_file_path(wxid)

            if not os.path.exists(reminders_file):
                logger.warning(f"提醒文件不存在: {reminders_file}")
                return JSONResponse(content={"success": False, "error": "未找到提醒记录"})

            with open(reminders_file, "r", encoding="utf-8") as f:
                try:
                    reminders = json.load(f)

                    for reminder in reminders:
                        if reminder.get("id") == id:
                            logger.info(f"找到提醒 {id} 的详情")
                            return JSONResponse(content={"success": True, "reminder": reminder})

                    logger.warning(f"未找到 ID 为 {id} 的提醒")
                    return JSONResponse(content={"success": False, "error": "未找到指定提醒"})

                except json.JSONDecodeError as e:
                    logger.error(f"解析 {wxid} 的提醒文件失败: {str(e)}")
                    return JSONResponse(content={"success": False, "error": f"解析提醒数据失败: {str(e)}"})

        except Exception as e:
            logger.exception(f"获取用户 {wxid} 的提醒 {id} 详情失败: {str(e)}")
            return JSONResponse(content={"success": False, "error": f"获取提醒详情失败: {str(e)}"})

    @app.put("/api/reminders/{wxid}/{id}", response_class=JSONResponse)
    async def api_update_reminder(wxid: str, id: int, request: Request, username: str = Depends(require_auth)):
        """更新提醒"""
        try:
            data = await request.json()
            content = data.get("content")
            reminder_type = data.get("reminder_type")
            reminder_time = data.get("reminder_time")
            chat_id = data.get("chat_id")

            logger.info(f"用户 {username} 更新 {wxid} 的提醒 {id}: {content}, 类型: {reminder_type}, 时间: {reminder_time}, 聊天ID: {chat_id}")

            if not all([content, reminder_type, reminder_time, chat_id]):
                logger.warning(f"更新提醒缺少必要参数: content={content}, type={reminder_type}, time={reminder_time}, chat_id={chat_id}")
                return JSONResponse(content={"success": False, "error": "缺少必要参数"})

            reminders_file = get_reminder_file_path(wxid)

            if not os.path.exists(reminders_file):
                logger.warning(f"提醒文件不存在: {reminders_file}")
                return JSONResponse(content={"success": False, "error": "未找到提醒记录"})

            try:
                with open(reminders_file, "r", encoding="utf-8") as f:
                    reminders = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"提醒文件 {reminders_file} 格式错误")
                return JSONResponse(content={"success": False, "error": "提醒文件格式错误"})

            reminder_updated = False
            for i, reminder in enumerate(reminders):
                if reminder.get("id") == id:
                    reminders[i] = {
                        "id": id,
                        "wxid": wxid,
                        "content": content,
                        "reminder_type": reminder_type,
                        "reminder_time": reminder_time,
                        "chat_id": chat_id,
                        "is_done": reminder.get("is_done", 0)
                    }
                    reminder_updated = True
                    break

            if not reminder_updated:
                logger.warning(f"未找到 ID 为 {id} 的提醒")
                return JSONResponse(content={"success": False, "error": "未找到指定提醒"})

            with open(reminders_file, "w", encoding="utf-8") as f:
                json.dump(reminders, f, ensure_ascii=False, indent=2)

            logger.info(f"成功更新用户 {wxid} 的提醒 {id}")
            return JSONResponse(content={"success": True})

        except Exception as e:
            logger.exception(f"更新提醒 {id} 失败: {str(e)}")
            return JSONResponse(content={"success": False, "error": f"更新提醒失败: {str(e)}"})

    @app.delete("/api/reminders/{wxid}/{id}", response_class=JSONResponse)
    async def api_delete_reminder(wxid: str, id: int, request: Request, username: str = Depends(require_auth)):
        """删除提醒"""
        try:
            logger.info(f"用户 {username} 删除 {wxid} 的提醒 {id}")

            reminders_file = get_reminder_file_path(wxid)

            if not os.path.exists(reminders_file):
                logger.warning(f"提醒文件不存在: {reminders_file}")
                return JSONResponse(content={"success": False, "error": "未找到提醒记录"})

            try:
                with open(reminders_file, "r", encoding="utf-8") as f:
                    reminders = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"提醒文件 {reminders_file} 格式错误")
                return JSONResponse(content={"success": False, "error": "提醒文件格式错误"})

            original_length = len(reminders)
            reminders = [r for r in reminders if r.get("id") != id]

            if len(reminders) == original_length:
                logger.warning(f"未找到 ID 为 {id} 的提醒")
                return JSONResponse(content={"success": False, "error": "未找到指定提醒"})

            with open(reminders_file, "w", encoding="utf-8") as f:
                json.dump(reminders, f, ensure_ascii=False, indent=2)

            logger.info(f"成功删除用户 {wxid} 的提醒 {id}")
            return JSONResponse(content={"success": True})

        except Exception as e:
            logger.exception(f"删除提醒 {id} 失败: {str(e)}")
            return JSONResponse(content={"success": False, "error": f"删除提醒失败: {str(e)}"})
