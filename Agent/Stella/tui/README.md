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