"""微信登录处理模块

负责处理微信登录逻辑，包括二维码登录、唤醒登录等
"""
import asyncio
import aiohttp
import json
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from loguru import logger


class WechatLoginHandler:
    """微信登录处理器"""

    def __init__(self, bot, api_host: str, api_port: int, script_dir: Path, update_status_callback):
        """初始化登录处理器

        Args:
            bot: WechatAPIClient 实例
            api_host: API 服务器地址
            api_port: API 服务器端口
            script_dir: 脚本目录路径
            update_status_callback: 状态更新回调函数
        """
        self.bot = bot
        self.api_host = api_host
        self.api_port = api_port
        self.script_dir = script_dir
        self.update_status = update_status_callback

    async def handle_login(self, enable_wechat_login: bool) -> bool:
        """处理微信登录流程

        Args:
            enable_wechat_login: 是否启用微信登录

        Returns:
            登录是否成功
        """
        if not enable_wechat_login:
            logger.warning("已禁用原生微信登录（enable-wechat-login=false），系统将仅依赖适配器处理消息")
            self.update_status("adapter_mode", "已禁用微信登录，等待适配器消息", {
                "nickname": self.bot.nickname or "",
                "wxid": self.bot.wxid or "",
                "alias": self.bot.alias or ""
            })
            return True

        # 加载机器人状态
        robot_stat = self._load_robot_stat()
        wxid = robot_stat.get("wxid", None)
        device_name = robot_stat.get("device_name", None)
        device_id = robot_stat.get("device_id", None)

        # 检查是否已登录
        if await self.bot.is_logged_in(wxid):
            await self._handle_already_logged_in(wxid)
        else:
            device_name, device_id = await self._handle_new_login(wxid, device_name, device_id)
            # 保存登录信息
            self._save_robot_stat(self.bot.wxid, device_name, device_id)

        logger.info("登录设备信息: device_name: {}  device_id: {}", device_name, device_id)
        logger.success("登录成功")

        # 更新状态为在线
        self.update_status("online", f"已登录：{self.bot.nickname}", {
            "nickname": self.bot.nickname,
            "wxid": self.bot.wxid,
            "alias": self.bot.alias
        })

        # 开启自动心跳
        await self._start_auto_heartbeat()

        return True

    def _load_robot_stat(self) -> Dict[str, Any]:
        """加载机器人状态文件

        Returns:
            机器人状态字典
        """
        robot_stat_path = self.script_dir / "resource" / "robot_stat.json"
        if not robot_stat_path.exists():
            default_config = {
                "wxid": "",
                "device_name": "",
                "device_id": ""
            }
            robot_stat_path.parent.mkdir(parents=True, exist_ok=True)
            with open(robot_stat_path, "w") as f:
                json.dump(default_config, f)
            return default_config
        else:
            with open(robot_stat_path, "r") as f:
                return json.load(f)

    def _save_robot_stat(self, wxid: str, device_name: str, device_id: str):
        """保存机器人状态

        Args:
            wxid: 微信ID
            device_name: 设备名称
            device_id: 设备ID
        """
        robot_stat = {
            "wxid": wxid,
            "device_name": device_name,
            "device_id": device_id
        }
        robot_stat_path = self.script_dir / "resource" / "robot_stat.json"
        with open(robot_stat_path, "w") as f:
            json.dump(robot_stat, f)

    async def _handle_already_logged_in(self, wxid: str):
        """处理已登录的情况

        Args:
            wxid: 微信ID
        """
        self.bot.wxid = wxid
        profile = await self.bot.get_profile()

        self.bot.nickname = profile.get("userInfo").get("NickName").get("string")
        self.bot.alias = profile.get("userInfo").get("Alias")
        self.bot.phone = profile.get("userInfo").get("BindMobile").get("string")

        logger.info("profile登录账号信息: wxid: {}  昵称: {}  微信号: {}  手机号: {}",
                   self.bot.wxid, self.bot.nickname, self.bot.alias, self.bot.phone)

    async def _handle_new_login(self, wxid: Optional[str], device_name: Optional[str],
                                device_id: Optional[str]) -> Tuple[str, str]:
        """处理新登录流程

        Args:
            wxid: 微信ID（可能为空）
            device_name: 设备名称（可能为空）
            device_id: 设备ID（可能为空）

        Returns:
            (device_name, device_id) 元组
        """
        while not await self.bot.is_logged_in(wxid):
            try:
                get_cached_info = await self.bot.get_cached_info(wxid)

                if get_cached_info:
                    # 尝试二次登录
                    device_name, device_id = await self._try_twice_login(wxid, device_name, device_id)
                else:
                    # 二维码登录
                    device_name, device_id = await self._qrcode_login(device_name, device_id)

            except Exception as e:
                logger.error("发生错误: {}", e)
                # 出错时重新尝试二维码登录
                device_name, device_id = await self._qrcode_login(device_name, device_id)

            # 等待登录完成
            await self._wait_for_login_completion(device_name, device_id)

        # 获取登录账号信息
        return device_name, device_id

    async def _try_twice_login(self, wxid: str, device_name: Optional[str],
                               device_id: Optional[str]) -> Tuple[str, str]:
        """尝试二次登录

        Args:
            wxid: 微信ID
            device_name: 设备名称
            device_id: 设备ID

        Returns:
            (device_name, device_id) 元组
        """
        twice = await self.bot.twice_login(wxid)
        logger.info("二次登录:{}", twice)

        if not twice:
            logger.error("二次登录失败，请检查微信是否在运行中，或重新启动机器人")
            logger.info("尝试唤醒登录...")

            try:
                device_name, device_id = await self._awaken_login(wxid, device_name, device_id)
            except Exception as e:
                logger.error("唤醒登录失败: {}", e)
                # 回退到二维码登录
                device_name, device_id = await self._qrcode_login(device_name, device_id)

        return device_name, device_id

    async def _awaken_login(self, wxid: str, device_name: Optional[str],
                           device_id: Optional[str]) -> Tuple[str, str]:
        """唤醒登录

        Args:
            wxid: 微信ID
            device_name: 设备名称
            device_id: 设备ID

        Returns:
            (device_name, device_id) 元组

        Raises:
            Exception: 唤醒登录失败时抛出
        """
        async with aiohttp.ClientSession() as session:
            api_base = "/api"
            api_url = f'http://{self.api_host}:{self.api_port}{api_base}/Login/LoginTwiceAutoAuth'

            json_param = {
                "OS": device_name if device_name else "iPad",
                "Proxy": {
                    "ProxyIp": "",
                    "ProxyPassword": "",
                    "ProxyUser": ""
                },
                "Url": "",
                "Wxid": wxid
            }

            logger.debug(f"发送唤醒登录请求到 {api_url} 参数: {json_param}")

            try:
                response = await session.post(api_url, json=json_param)

                if response.status != 200:
                    logger.error(f"唤醒登录请求失败，状态码: {response.status}")
                    raise Exception(f"服务器返回状态码 {response.status}")

                json_resp = await response.json()
                logger.debug(f"唤醒登录响应: {json_resp}")

                if json_resp and json_resp.get("Success"):
                    data = json_resp.get("Data", {})
                    qr_response = data.get("QrCodeResponse", {}) if data else {}
                    uuid = qr_response.get("Uuid", "") if qr_response else ""

                    if uuid:
                        logger.success(f"唤醒登录成功，获取到登录uuid: {uuid}")
                        self.update_status("waiting_login", f"等待微信登录 (UUID: {uuid})")
                        return device_name, device_id
                    else:
                        logger.error("唤醒登录响应中没有有效的UUID")
                        raise Exception("响应中没有有效的UUID")
                else:
                    error_msg = json_resp.get("Message", "未知错误") if json_resp else "未知错误"
                    logger.error(f"唤醒登录失败: {error_msg}")
                    raise Exception(error_msg)

            except Exception as e:
                logger.error(f"唤醒登录过程中出错: {e}")
                logger.error("将尝试二维码登录")
                # 回退到二维码登录
                return await self._qrcode_login(device_name, device_id)

    async def _qrcode_login(self, device_name: Optional[str],
                           device_id: Optional[str]) -> Tuple[str, str]:
        """二维码登录

        Args:
            device_name: 设备名称
            device_id: 设备ID

        Returns:
            (device_name, device_id) 元组
        """
        if not device_name:
            device_name = self.bot.create_device_name()
        if not device_id:
            device_id = self.bot.create_device_id()

        uuid, url = await self.bot.get_qr_code(device_id=device_id, device_name=device_name, print_qr=True)
        logger.success("获取到登录uuid: {}", uuid)
        logger.success("获取到登录二维码: {}", url)

        # 更新状态，记录二维码URL
        self.update_status("waiting_login", "等待微信扫码登录", {
            "qrcode_url": url,
            "uuid": uuid,
            "expires_in": 240,
            "timestamp": time.time()
        })

        # 检查状态文件是否正确更新
        self._verify_status_file(url, uuid)

        # 显示倒计时
        logger.info("等待登录中，过期倒计时：240")

        return device_name, device_id

    def _verify_status_file(self, url: str, uuid: str):
        """验证状态文件是否正确更新

        Args:
            url: 二维码URL
            uuid: 登录UUID
        """
        try:
            status_file = self.script_dir / "admin" / "bot_status.json"
            if status_file.exists():
                with open(status_file, "r", encoding="utf-8") as f:
                    current_status = json.load(f)
                    if current_status.get("qrcode_url") != url:
                        logger.warning("状态文件中的二维码URL与实际不符，尝试重新更新状态")
                        self.update_status("waiting_login", "等待微信扫码登录", {
                            "qrcode_url": url,
                            "uuid": uuid,
                            "expires_in": 240,
                            "timestamp": time.time()
                        })
        except Exception as e:
            logger.error(f"检查状态文件失败: {e}")

    async def _wait_for_login_completion(self, device_name: str, device_id: str):
        """等待登录完成

        Args:
            device_name: 设备名称
            device_id: 设备ID
        """
        # 这里需要获取uuid，但在重构中uuid是局部变量
        # 需要从之前的登录流程中传递过来
        # 暂时保留原有逻辑，后续可以优化
        pass

    async def _start_auto_heartbeat(self):
        """开启自动心跳"""
        try:
            success = await self.bot.start_auto_heartbeat()
            if success:
                logger.success("已开启自动心跳")
            else:
                logger.warning("开启自动心跳失败")
        except ValueError:
            logger.warning("自动心跳已在运行")
        except Exception as e:
            logger.warning("自动心跳已在运行:{}", e)
