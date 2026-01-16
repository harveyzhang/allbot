# AllBot 插件开发指南 🧩

欢迎来到 AllBot 插件开发指南！AllBot 是一个基于插件架构的智能助手系统，你可以轻松扩展其功能。

---

## 一、 插件目录结构

每个插件都是 `plugins/` 目录下的一个文件夹。一个标准插件的典型结构如下：

```text
plugins/YourPlugin/
├── __init__.py      # 插件标识文件
├── config.toml      # 插件配置文件 (可选)
├── main.py          # 插件逻辑核心 (必须)
└── README.md        # 插件说明文档
```

---

## 二、 基础开发模板

插件必须继承 `utils.plugin_base.PluginBase` 类，并使用装饰器来监听消息。

```python:plugins/YourPlugin/main.py
import tomllib
from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase

class YourPlugin(PluginBase):
    description = "这是一个示例插件"
    author = "您的名字"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        # 加载插件配置 (示例)
        # with open("plugins/YourPlugin/config.toml", "rb") as f:
        #     self.config = tomllib.load(f)

    @on_text_message(priority=10)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        """处理文本消息"""
        content = message.get("Content", "")
        if content == "你好":
            from_wxid = message.get("FromWxid")
            await bot.send_text_message(from_wxid, "你好！我是您的助手。")
```

---

## 三、 常用消息监听装饰器

你可以通过在方法上添加装饰器来捕获不同类型的微信消息：

- `@on_text_message(priority=10)`: 监听文本消息。
- `@on_at_message(priority=10)`: 监听在群里被 @ 的消息。
- `@on_image_message(priority=10)`: 监听图片消息。
- `@on_voice_message(priority=10)`: 监听语音消息。
- `@on_file_message(priority=10)`: 监听文件消息。
- `@on_quote_message(priority=10)`: 监听引用消息。
- `@on_xml_message(priority=10)`: 监听 XML 格式消息。

> **提示**: `priority` 数值越小，插件处理消息的优先级越高。

---

## 四、 微信 API 调用 (WechatAPIClient)

在监听方法中，你可以使用 `bot` 对象调用各种 API：

| 功能 | 方法 | 示例参数 |
| :--- | :--- | :--- |
| 发送文本 | `send_text_message` | `(to_wxid, content)` |
| 发送图片 | `send_image_message` | `(to_wxid, image_data)` |
| 发送语音 | `send_voice_message` | `(to_wxid, voice_data, format="mp3")` |
| 发送 @ 消息 | `send_at_message` | `(room_wxid, content, at_list)` |
| 获取昵称 | `get_nickname` | `(wxid)` |
| 下载图片 | `get_msg_image` | `(msg_id, from_wxid, ...)` |

---

## 五、 插件开发规范

1.  **独立配置**: 尽量将插件特有的配置放在插件目录下的 `config.toml` 中。
2.  **异常处理**: 插件内部逻辑应包含 `try...except`，避免单个插件崩溃导致整个系统异常。
3.  **不阻塞异步**: 避免在处理方法中使用 `time.sleep()`，请使用 `await asyncio.sleep()`。
4.  **资源清理**: 插件产生的临时文件请及时清理（可利用 `utils.files_cleanup` 模块）。

---

## 六、 插件市场

如果你希望将插件分享给其他用户，请在 `README.md` 中提供详细的安装和使用说明，并包含必要的打赏链接以支持你的开发。
