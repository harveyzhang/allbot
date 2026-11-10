<!-- AUTO-DOC: Update me when files in this folder change -->

# AssistantPlugin

SSE 流式 AI 对话小助手插件支持 @ 提及、触发词和引用消息。引用附件通过网关上传，文件来源限定在框架媒体目录和协议缓存目录。私聊与群聊使用各自的会话。

## Files

| File | Role | Function |
|------|------|----------|
| main.py | Core | 加载配置、组装引用文本与附件路径、处理流式回复并校验管理员权限 |
| config.toml | Config | 开关、触发词、管理员列表、image-public-base-url 等配置项 |
| __init__.py | Export | 导出 AssistantPlugin |
