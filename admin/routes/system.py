"""
系统管理路由模块

职责：处理系统监控、配置管理、日志查看等 API
"""
import os
import socket
import platform
from datetime import datetime
from fastapi import Request, Depends
from fastapi.responses import JSONResponse, FileResponse
from loguru import logger

# 导入 tomllib
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def register_system_routes(app, get_system_info, get_system_status, handle_system_stats, current_dir):
    """
    注册系统管理相关路由

    Args:
        app: FastAPI 应用实例
        get_system_info: 获取系统信息函数
        get_system_status: 获取系统状态函数
        handle_system_stats: 处理系统统计函数
        current_dir: 当前目录路径
    """
    from admin.utils import require_auth

    @app.get("/api/system/status", response_class=JSONResponse, tags=["系统"])
    async def api_system_status(username: str = Depends(require_auth)):
        """获取系统状态"""
        return {
            "success": True,
            "data": get_system_status()
        }


    @app.get("/api/system/stats", response_class=JSONResponse, tags=["系统"])
    async def api_system_stats(request: Request, type: str = "system", time_range: str = "1", username: str = Depends(require_auth)):
        """
        系统统计 API

        参数:
            type: 统计类型，可选值: messages(消息统计), system(系统信息)
            time_range: 时间范围，仅在 type=messages 时有效，可选值: 1(今天), 7(本周), 30(本月)
        """
        logger.info(f"用户 {username} 请求系统统计数据，类型: {type}, 范围: {time_range}")

        # 调用 system_stats_api 模块中的处理函数
        return await handle_system_stats(request, type, time_range)


    @app.get("/api/system/info", response_class=JSONResponse, tags=["系统"])
    async def api_system_info(username: str = Depends(require_auth)):
        """获取系统信息"""
        try:
            info = get_system_info()
            return {
                "success": True,
                "data": info,
                "error": None
            }
        except Exception as e:
            logger.error(f"获取系统信息 API 失败: {str(e)}")
            # 返回默认值但标记为成功，避免前端显示错误
            return JSONResponse(content={
                "success": True,
                "data": {
                    "hostname": socket.gethostname() if hasattr(socket, 'gethostname') else "unknown",
                    "platform": platform.platform() if hasattr(platform, 'platform') else "unknown",
                    "python_version": platform.python_version() if hasattr(platform, 'python_version') else "unknown",
                    "cpu_count": 0,
                    "memory_total": 0,
                    "memory_available": 0,
                    "disk_total": 0,
                    "disk_free": 0,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "error": str(e)
            })


    @app.get("/api/system/config", response_class=JSONResponse, tags=["系统"])
    async def api_get_system_config(username: str = Depends(require_auth)):
        """获取系统配置的结构化数据"""
        try:
            if tomllib is None:
                return {"success": False, "error": "tomllib 库不可用"}

            # 读取配置文件
            main_config_path = os.path.join(os.path.dirname(current_dir), "main_config.toml")
            if not os.path.exists(main_config_path):
                return {"success": False, "error": "配置文件不存在"}

            with open(main_config_path, "rb") as f:
                config_data = tomllib.load(f)

            return {
                "success": True,
                "data": config_data
            }
        except Exception as e:
            logger.error(f"获取系统配置失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @app.post("/api/system/config", response_class=JSONResponse, tags=["系统"])
    async def api_save_system_config(request: Request, username: str = Depends(require_auth)):
        """保存系统配置的结构化数据"""
        try:
            # 获取请求体
            config_data = await request.json()

            # 配置文件路径
            main_config_path = os.path.join(os.path.dirname(current_dir), "main_config.toml")

            # 将配置转换为 TOML 格式并保存
            try:
                import toml
                with open(main_config_path, "w", encoding="utf-8") as f:
                    toml.dump(config_data, f)
            except ImportError:
                # 如果没有 toml 库，使用简单的字符串拼接
                logger.warning("toml 库不可用，使用简单格式保存")
                with open(main_config_path, "w", encoding="utf-8") as f:
                    f.write("# AllBot 配置文件\n")
                    for section, values in config_data.items():
                        f.write(f"\n[{section}]\n")
                        for key, value in values.items():
                            if isinstance(value, str):
                                f.write(f'{key} = "{value}"\n')
                            elif isinstance(value, bool):
                                f.write(f'{key} = {str(value).lower()}\n')
                            else:
                                f.write(f'{key} = {value}\n')

            return {
                "success": True,
                "message": "配置保存成功"
            }
        except Exception as e:
            logger.error(f"保存系统配置失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @app.get("/api/system/logs", response_class=JSONResponse, tags=["系统"])
    async def api_system_logs(lines: int = 100, username: str = Depends(require_auth)):
        """
        获取系统日志

        参数:
            lines: 返回的日志行数，默认 100
        """
        try:
            # 查找日志文件
            logs_dir = os.path.join(os.path.dirname(current_dir), "logs")
            if not os.path.exists(logs_dir):
                return {
                    "success": False,
                    "error": "日志目录不存在"
                }

            # 获取最新的日志文件
            log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
            if not log_files:
                return {
                    "success": False,
                    "error": "没有找到日志文件"
                }

            # 按修改时间排序，获取最新的
            log_files.sort(key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)), reverse=True)
            latest_log = os.path.join(logs_dir, log_files[0])

            # 读取最后 N 行
            with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            return {
                "success": True,
                "data": {
                    "logs": "".join(log_lines),
                    "file": log_files[0],
                    "total_lines": len(all_lines)
                }
            }
        except Exception as e:
            logger.error(f"获取系统日志失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


    @app.get("/api/system/logs/download", response_class=FileResponse, tags=["系统"])
    async def api_download_logs(username: str = Depends(require_auth)):
        """下载系统日志文件"""
        try:
            # 查找日志文件
            logs_dir = os.path.join(os.path.dirname(current_dir), "logs")
            if not os.path.exists(logs_dir):
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": "日志目录不存在"}
                )

            # 获取最新的日志文件
            log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
            if not log_files:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": "没有找到日志文件"}
                )

            # 按修改时间排序，获取最新的
            log_files.sort(key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)), reverse=True)
            latest_log = os.path.join(logs_dir, log_files[0])

            return FileResponse(
                path=latest_log,
                filename=log_files[0],
                media_type="text/plain"
            )
        except Exception as e:
            logger.error(f"下载日志文件失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": str(e)}
            )

    logger.info("系统管理路由注册完成")
