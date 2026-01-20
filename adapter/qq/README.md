# QQ 适配器

[← 返回主文档](../../README.md) | [适配器总览](../CLAUDE.md)

---

## 📝 概述

QQ 适配器用于对接 NTQQ 协议，实现 AllBot 在 QQ 平台上的消息收发功能。通过 Redis 消息队列与主程序通信，支持私聊和群聊场景。

## ✨ 功能特性

- 🐧 **NTQQ 协议**：基于 NTQQ 协议实现消息收发
- 💬 **私聊/群聊**：支持一对一对话和群组消息
- 🔄 **消息队列**：通过 Redis 异步通信
- ⚡ **异步处理**：全异步架构，高效处理

## 🏗️ 架构设计

```
NTQQ 客户端 → QQ 适配器 → Redis 队列 → 主程序核心 → 插件处理
```

## ⚙️ 配置说明

在 `main_config.toml` 中配置：

```toml
[adapter]
enabled = true  # 启用适配器功能

[adapter.qq]
enable = true   # 启用 QQ 适配器

# Redis 配置
redis-host = "127.0.0.1"
redis-port = 6379

# 队列配置
main-queue = "allbot"
reply-queue = "allbot_reply:qq"
```

### 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable` | boolean | false | 是否启用 QQ 适配器 |
| `redis-host` | string | "127.0.0.1" | Redis 服务器地址 |
| `redis-port` | integer | 6379 | Redis 端口 |
| `main-queue` | string | "allbot" | 主消息队列 |
| `reply-queue` | string | "allbot_reply:qq" | QQ 回复队列 |

## 🚀 使用方法

1. **安装 NTQQ**：安装并配置 NTQQ 客户端
2. **启动 Redis**：`redis-server`
3. **配置适配器**：编辑 `main_config.toml`
4. **启动主程序**：`python main.py`

## 🔧 消息格式

```python
{
    "platform": "qq",
    "message_type": "text",
    "from_wxid": "qq_user_id",
    "to_wxid": "bot_qq_id",
    "content": "消息内容",
    "is_group": false,
    "group_id": "",
    "timestamp": 1234567890
}
```

## 🔴 常见问题

**无法连接 NTQQ**
- 确认 NTQQ 客户端正常运行
- 检查 API 接口是否开启
- 查看日志 `logs/allbot_*.log`

**Redis 连接失败**
- 确认 Redis 服务运行中
- 检查配置中的地址和端口
- 确认防火墙允许访问

**消息无法发送**
- 检查 Redis 回复队列
- 确认 NTQQ 客户端在线
- 查看日志错误信息

**适配器未启动**
- 确认 `adapter.enabled = true` 和 `adapter.qq.enable = true`
- 检查主程序日志中的加载信息

## 📚 相关文档

- [多平台适配器说明](../../docs/multi-platform-adapter.md)
- [配置指南](../../docs/配置指南.md)
- [系统架构文档](../../docs/系统架构文档.md)

## 🔗 相关链接

- [NTQQ 项目](https://github.com/NapNeko/NapCatQQ)
- [Redis 官方文档](https://redis.io/documentation)

---

**注意**：QQ 适配器目前处于实验阶段，部分功能可能不稳定。如遇问题请及时反馈。
