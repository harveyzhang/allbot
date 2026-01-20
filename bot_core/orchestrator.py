"""主编排器模块

重构后的 bot_core() 函数，使用组合模式将各个功能模块组合起来
"""
import os
from pathlib import Path

from loguru import logger

from utils.config_manager import get_config
from bot_core.client_initializer import ClientInitializer
from bot_core.login_handler import WechatLoginHandler
from bot_core.service_initializer import ServiceInitializer
from bot_core.message_listener import MessageListener
from bot_core.status_manager import update_bot_status, set_bot_instance


async def bot_core():
    """Bot 核心启动函数 - 重构后的清晰编排器

    职责：
    1. 设置工作目录
    2. 加载配置
    3. 初始化客户端
    4. 处理登录
    5. 初始化服务
    6. 启动消息监听

    Returns:
        XYBot 实例
    """
    # ========== 1. 设置工作目录 ==========
    script_dir = Path(__file__).resolve().parent.parent
    os.chdir(script_dir)

    update_bot_status("initializing", "系统初始化中")

    try:
        # ========== 2. 加载配置 ==========
        logger.info("📋 开始加载配置...")
        app_config = get_config()
        logger.success("✅ 配置加载完成")

        # ========== 3. 初始化客户端 ==========
        logger.info("🔌 开始初始化WechatAPI客户端...")
        client_initializer = ClientInitializer(app_config, script_dir)
        bot = client_initializer.initialize_client()
        logger.success("✅ 客户端初始化完成")

        update_bot_status("waiting_login", "等待微信登录")

        # ========== 4. 处理登录 ==========
        logger.info("🔐 开始处理微信登录...")
        login_handler = WechatLoginHandler(
            bot=bot,
            api_host=app_config.wechat_api.host,
            api_port=app_config.wechat_api.port,
            script_dir=script_dir,
            update_status_callback=update_bot_status
        )

        await login_handler.handle_login(app_config.xybot.enable_wechat_login)
        logger.success("✅ 登录处理完成")

        # ========== 5. 初始化服务 ==========
        logger.info("⚙️ 开始初始化服务...")
        service_initializer = ServiceInitializer(bot, app_config, script_dir)
        xybot, message_db, keyval_db, notification_service = await service_initializer.initialize_all_services()

        # 设置机器人实例到管理后台
        set_bot_instance(xybot)

        # 启动自动重启监控器
        service_initializer.start_auto_restart_monitor()

        logger.success("✅ 服务初始化完成")

        update_bot_status("ready", "机器人已准备就绪")
        logger.success("🚀 开始处理消息")

        # ========== 6. 启动消息监听 ==========
        logger.info("👂 开始启动消息监听...")
        message_listener = MessageListener(xybot, app_config, script_dir)
        await message_listener.start_listening(message_db)

        # 正常情况下不会执行到这里，因为消息监听会阻塞
        return xybot

    except Exception as e:
        logger.error(f"❌ bot_core 启动失败: {e}")
        logger.error("详细错误信息:", exc_info=True)
        update_bot_status("error", f"启动失败: {e}")
        raise
