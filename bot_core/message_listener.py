"""消息监听模块

负责WebSocket消息监听和Redis消息消费
"""
import asyncio
import json
import time
import traceback
from typing import Dict, Any
from pathlib import Path

import websockets
import redis.asyncio as aioredis
from loguru import logger

from utils.config_manager import AppConfig
from utils.message_normalizer import MessageNormalizer


QUEUE_NAME = 'allbot'  # 自定义队列名


async def message_consumer(xybot, redis, message_db):
    """消息消费者，从Redis队列中消费消息

    Args:
        xybot: XYBot 实例
        redis: Redis 客户端
        message_db: 消息数据库实例
    """
    while True:
        _, msg_json = await redis.blpop(QUEUE_NAME)
        message = json.loads(msg_json)
        logger.info(f"消息已出队并开始处理，队列: {QUEUE_NAME}，消息ID: {message.get('MsgId') or message.get('msgId')}")
        try:
            await xybot.process_message(message)
        except Exception as e:
            logger.error(f"消息处理异常: {e}")


async def listen_ws_messages(xybot, ws_url, redis, message_db):
    """WebSocket 客户端，实时接收消息并处理，自动重连，依赖官方ping/pong心跳机制

    Args:
        xybot: XYBot 实例
        ws_url: WebSocket URL
        redis: Redis 客户端
        message_db: 消息数据库实例
    """
    reconnect_interval = 5  # 断开后重连间隔秒数
    reconnect_count = 0

    while True:
        try:
            if not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
                ws_url = "ws://" + ws_url

            logger.info(f"正在连接到 WebSocket 服务器: {ws_url}")

            async with websockets.connect(ws_url, ping_interval=30, ping_timeout=10) as websocket:
                logger.success(f"已连接到 WebSocket 消息服务器: {ws_url}")
                reconnect_count = 0  # 成功连接后重置重连计数

                while True:
                    try:
                        msg = await websocket.recv()

                        # 检查服务端主动关闭连接的业务消息
                        if isinstance(msg, str) and ("已关闭连接" in msg or "connection closed" in msg.lower()):
                            logger.warning("检测到服务端主动关闭连接消息，主动关闭本地ws，准备重连...")
                            await websocket.close()
                            break

                        try:
                            data = json.loads(msg)
                            await _process_ws_message(data, xybot, redis, message_db)

                        except json.JSONDecodeError:
                            msg_preview = msg[:100] + "..." if len(msg) > 100 else msg
                            if not msg.strip():
                                logger.debug("收到WebSocket心跳包或空消息")
                            else:
                                logger.info(f"收到非JSON格式的WebSocket消息: {msg_preview}")

                        except Exception as e:
                            logger.error(f"处理ws消息出错: {e}, 原始内容: {msg[:100]}...")

                    except websockets.exceptions.ConnectionClosed as e:
                        logger.error(f"WebSocket 连接已关闭: {e} (code={getattr(e, 'code', None)}, reason={getattr(e, 'reason', None)})，检测到断链，{reconnect_interval}秒后重连...")
                        break

                    except Exception as e:
                        logger.error(f"WebSocket消息主循环异常: {e}\n{traceback.format_exc()}，{reconnect_interval}秒后重连...")
                        break

        except Exception as e:
            reconnect_count += 1
            logger.error(f"WebSocket 连接失败: {type(e).__name__}: {e}，第{reconnect_count}次重连，{reconnect_interval}秒后重试...\n{traceback.format_exc()}")
            await asyncio.sleep(reconnect_interval)


async def _process_ws_message(data: Dict[str, Any], xybot, redis, message_db):
    """处理WebSocket消息

    Args:
        data: 消息数据
        xybot: XYBot 实例
        redis: Redis 客户端
        message_db: 消息数据库实例
    """
    if isinstance(data, dict) and "AddMsgs" in data:
        # 标准格式消息
        messages = data["AddMsgs"]
        for message in messages:
            await _save_and_enqueue_message(message, redis, message_db, is_standard_format=True)
    else:
        # 自定义格式消息，使用 MessageNormalizer 转换
        ws_msg = data
        ws_msgs = [ws_msg] if isinstance(ws_msg, dict) else ws_msg

        for msg in ws_msgs:
            # 使用 MessageNormalizer 进行格式转换
            addmsg = MessageNormalizer.convert_to_standard_format(msg, getattr(xybot.bot, "wxid", ""))
            logger.info(f"ws消息适配为AddMsgs: {json.dumps(addmsg, ensure_ascii=False)}")
            await _save_and_enqueue_message(addmsg, redis, message_db, is_standard_format=False)


async def _save_and_enqueue_message(message: Dict[str, Any], redis, message_db, is_standard_format: bool):
    """保存消息到数据库并入队

    Args:
        message: 消息数据
        redis: Redis 客户端
        message_db: 消息数据库实例
        is_standard_format: 是否为标准格式
    """
    # 使用 MessageNormalizer 提取消息字段
    fields = MessageNormalizer.extract_message_fields(message, is_standard_format)

    # 保存到数据库
    await message_db.save_message(
        msg_id=fields["msg_id"],
        sender_wxid=fields["sender_wxid"],
        from_wxid=fields["from_wxid"],
        msg_type=fields["msg_type"],
        content=fields["content"],
        is_group=False  # 可根据业务调整
    )

    # 入队
    await redis.rpush(QUEUE_NAME, json.dumps(message, ensure_ascii=False))
    logger.info(f"消息已入队到队列 {QUEUE_NAME}，消息ID: {fields['msg_id']}")


class MessageListener:
    """消息监听器"""

    def __init__(self, xybot, config: AppConfig, script_dir: Path):
        """初始化消息监听器

        Args:
            xybot: XYBot 实例
            config: 应用配置对象
            script_dir: 脚本目录路径
        """
        self.xybot = xybot
        self.config = config
        self.script_dir = script_dir
        self.redis = None
        self.consumer_tasks = []

    async def start_listening(self, message_db):
        """启动消息监听

        Args:
            message_db: 消息数据库实例
        """
        api_config = self.config.wechat_api

        # 初始化 Redis 连接
        redis_url = f"redis://{api_config.redis_host}:{api_config.redis_port}"
        self.redis = aioredis.from_url(redis_url, decode_responses=True)

        # 启动消息消费者
        num_consumers = 1  # 可根据需要调整
        self.consumer_tasks = [
            asyncio.create_task(message_consumer(self.xybot, self.redis, message_db))
            for _ in range(num_consumers)
        ]

        try:
            # 根据配置决定是否启用 WebSocket
            if api_config.enable_websocket:
                ws_url = self._get_websocket_url()
                logger.info(f"WebSocket 消息推送地址: {ws_url}")
                await listen_ws_messages(self.xybot, ws_url, self.redis, message_db)
            else:
                logger.info("WebSocket 消息通道已禁用（enable-websocket = false），消息消费者将继续从 Redis 队列读取")
                # 阻塞当前协程，保持消费者持续运行
                await asyncio.Event().wait()

        finally:
            for task in self.consumer_tasks:
                task.cancel()
            await asyncio.gather(*self.consumer_tasks, return_exceptions=True)

    def _get_websocket_url(self) -> str:
        """获取WebSocket URL

        Returns:
            WebSocket URL
        """
        api_config = self.config.wechat_api
        ws_url = api_config.ws_url

        # 如果配置中没有 ws_url，构造默认值
        if not ws_url or not isinstance(ws_url, str):
            server_host = api_config.host
            server_port = api_config.ws_port or api_config.port
            ws_url = f"ws://{server_host}:{server_port}/ws"
            logger.warning(f"未在配置中找到有效的 ws-url，使用构造值: {ws_url}")

        # 添加 wxid 到 URL
        wxid = self.xybot.bot.wxid
        if wxid and not ws_url.rstrip("/").endswith(wxid):
            ws_url = ws_url.rstrip("/") + f"/{wxid}"

        return ws_url
