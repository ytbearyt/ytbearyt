# Stella TUI

Stella 仅包含两个顶层模块目录：`core/` 与 `tui/`。`core` 提供 UI 无关的会话服务，`tui` 是基于 Textual 的终端界面。未来其他界面适配器可以作为并列目录加入。

## 配置

在 Stella 目录下执行：

```powershell
Copy-Item core/config.example.ini core/config.ini
```

编辑 `core/config.ini` 填入模型服务参数。配置文件被 `core/.gitignore` 忽略，不应提交凭据。也可以使用 `STELLA_API_KEY`、`STELLA_BASE_URL` 和 `STELLA_MODEL` 环境变量覆盖配置。

## 安装与启动

在工作区根目录执行：

```powershell
python -m pip install -r Agent/Stella/tui/requirements.txt
python -m Agent.Stella.tui
```

`core.ChatSession.send(prompt)` 返回 `ChatEvent` 事件流，供不同界面复用；core 不依赖 Textual。