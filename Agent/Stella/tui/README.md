## 斜杠命令

输入 `/` 会显示命令补全引导。常用命令如下：
| 命令 | 作用 |
| --- | --- |
| `/new` | 自动保存当前会话并新建会话 |
| `/resume` | 打开历史会话列表；上下键选择、回车恢复、Esc 取消 |
| `/save` | 保存当前会话 |
| `/compact` | 压缩当前上下文 |
| `/clear` | 清空当前界面显示，不删除历史 |
| `/status` | 显示会话 ID 和上下文状态 |
| `/mcp` | 提示 MCP 状态所在的左侧栏 |
| `/help` | 显示全部命令 |
| `/quit` | 退出 Stella |
会话以可读的 JSONL 事件日志保存到 `.agents/sessions/`。如果项目根目录存在 `AGENTS.md`，Stella 首次创建会话时会将它作为一次性系统消息注入，并在后续轮次复用。

## 配置

Stella 从启动工作目录读取 `config.ini`。如果文件不存在，会自动生成包含 mock 值的完整配置并弹窗提示；请填写 `[llm]` 后重新启动。配置还包括 `[context]`、`[tools]` 和 `[storage]`，可调整上下文窗口、告警比例、文件读取上限、CLI/网页超时、检索结果长度和会话目录。环境变量 `STELLA_API_KEY`、`STELLA_BASE_URL`、`STELLA_MODEL` 以及对应的 `STELLA_*` 参数可以覆盖配置文件。
启动后 TUI 左侧栏会先显示 MCP 加载状态；后台异步发现完成后，动态列出当前已连接的 MCP Server 及其 tools。
# Stella TUI

Stella 仅包含两个顶层模块目录：`core/` 与 `tui/`。`core` 提供 UI 无关的会话服务，`tui` 是基于 Textual 的终端界面。未来其他界面适配器可以作为并列目录加入。

## 配置

在 Stella 目录下执行：

```powershell
Copy-Item core/config.example.ini core/config.ini
```

编辑 `core/config.ini` 填入模型服务参数。配置文件被 `core/.gitignore` 忽略，不应提交凭据。也可以使用 `STELLA_API_KEY`、`STELLA_BASE_URL` 和 `STELLA_MODEL` 环境变量覆盖配置。

## Agent Skills

Stella 启动时以启动工作目录为项目根目录，扫描 `.agents/skills/<skill>/SKILL.md`。每个 Skill 的文件必须以 YAML Frontmatter 开头，并包含 `name` 与 `description` 字段：

```markdown
---
name: example
description: An example skill.
---
```

初始化阶段只注册这些元数据；Skill 正文不会被读取。

对话中可通过 `loadSkill` 工具按需加载 Skill：只提供 `name` 时读取 `SKILL.md` 全文，提供 `filename` 时读取 Skill 目录内的附加文件。`filename` 支持 Skill 相对路径、项目相对路径和绝对路径；仅提供文件名时会递归搜索，多个匹配结果会返回候选路径。所有读取均限制在对应 Skill 目录内。

对话中可通过 `createSkill` 工具创建 Skill。`name` 必须使用小写字母、数字和连字符，`skillContext` 必须是包含 YAML Frontmatter、`name` 和 `description` 的完整 `SKILL.md` 内容。工具不会覆盖已有 Skill，创建成功后当前会话会立即更新可用 Skill 列表。若需要 `references/`、`scripts/` 等附加目录或文件，请继续使用现有文件操作工具创建。

## 安装与启动

在工作区根目录执行：

```powershell
python -m pip install -r Agent/Stella/tui/requirements.txt
python -m Agent.Stella.tui
```

`core.ChatSession.send(prompt)` 返回 `ChatEvent` 事件流，供不同界面复用；core 不依赖 Textual。

## 上下文管理

输入 `/compact` 可手动压缩当前会话。压缩前的完整消息会按 `YYYYMMDD-HHMMSS.jsonl` 保存到启动工作目录的 `.agents/context/`，压缩摘要会替换旧的对话历史；压缩期间不会执行普通工具调用。

上下文达到模型窗口的 70% 后，普通提示词会暂停，需先执行 `/compact`。TUI 底部会显示当前使用量、窗口大小和百分比；没有配置窗口大小时使用 128k，并标注“默认”。可在 `[llm]` 中设置 `context_window`，也可使用 `STELLA_CONTEXT_WINDOW` 环境变量覆盖。

模型可以通过 `recallContext` 工具按关键词检索 `.agents/context/` 中的原始 JSONL 归档；该工具支持可选的归档 `id` 和必需的 `text` 参数。