import re
import tomllib

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class BotStatus(PluginBase):
    description = "机器人状态"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/BotStatus/config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["BotStatus"]
        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command = config["command"]
        self.version = main_config["version"]
        self.status_message = config["status-message"]

    @on_text_message(priority=60)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        from loguru import logger
        logger.critical(f"[BotStatus] 收到消息调用: {message.get('Content', '')}")

        if not self.enable:
            logger.debug("[BotStatus] 插件未启用")
            return True

        content = str(message.get("Content", "")).strip()
        command = content.split(" ")

        logger.info(f"[BotStatus] 解析命令: {command}, 配置命令: {self.command}")

        if not len(command) or command[0] not in self.command:
            logger.debug(f"[BotStatus] 命令不匹配，继续执行")
            return True

        logger.info(f"[BotStatus] 命令匹配，准备发送状态消息")
        target_wxid = message.get("FromWxid")
        logger.critical(f"[BotStatus] 🎯 发送目标 FromWxid: {target_wxid}")
        logger.critical(f"[BotStatus] 🎯 完整消息对象: {message}")
        out_message = (f"{self.status_message}\n"
                       f"当前版本: {self.version}\n"
                       "项目地址：https://github.com/sxkiss/allbot\n")
        await bot.send_text_message(target_wxid, out_message)
        logger.critical(f"[BotStatus] ✅ 状态消息已发送到 {target_wxid}，阻止后续插件")
        return False

    @on_at_message(priority=60)
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        from loguru import logger
        logger.critical(f"[BotStatus] 收到@消息调用: {message.get('Content', '')}")

        if not self.enable:
            logger.debug("[BotStatus] 插件未启用")
            return True

        content = str(message.get("Content", "")).strip()
        command = re.split(r'[\s\u2005]+', content)

        logger.info(f"[BotStatus] 解析@命令: {command}, 配置命令: {self.command}")

        if len(command) < 2 or command[1] not in self.command:
            logger.debug(f"[BotStatus] @命令不匹配，继续执行")
            return True

        logger.info(f"[BotStatus] @命令匹配，准备发送状态消息")
        out_message = (f"{self.status_message}\n"
                       f"当前版本: {self.version}\n"
                       "项目地址：https://github.com/sxkiss/allbot\n")
        await bot.send_text_message(message.get("FromWxid"), out_message)
        logger.info(f"[BotStatus] @状态消息已发送，阻止后续插件")
        return False
