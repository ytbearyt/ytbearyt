# LLM 学习与实践

本仓库用于记录大语言模型应用及相关工具的学习实践，包含命令行对话、工具调用、MCP 服务、终端聊天应用和网页演示等内容。

## 项目目录

| 路径 | 内容 |
| --- | --- |
| [`Agent/Practice01`](Agent/Practice01) | 基础 LLM 对话与流式输出练习 |
| [`Agent/Practice02`](Agent/Practice02) | 模型工具调用及本地文件操作练习，包含多个迭代版本和架构图 |
| [`Agent/Stella`](Agent/Stella) | 分层设计的终端聊天应用，支持会话管理、工具调用和 MCP 等能力；详见 [`TUI 使用说明`](Agent/Stella/tui/README.md) |
| [`AnythingLLM_MCP`](AnythingLLM_MCP) | 将 AnythingLLM 工作区能力封装为 MCP 工具的服务 |
| [`AnythingLLMServer`](AnythingLLMServer) | AnythingLLM 相关网页文件 |
| [`petHospital_MCP`](petHospital_MCP) | 宠物医院管理系统及 REST API；详见[项目说明](petHospital_MCP/README.md) |
| [`ppt_neusoft`](ppt_neusoft) | 网页形式的演示文稿，入口为 [`index.html`](ppt_neusoft/index.html) |
| [`ppt_self_intro`](ppt_self_intro) | 个人介绍演示文稿及相关素材 |

## 环境要求

- Python 3.10 或更高版本（Python 项目）
- Go（从源码构建宠物医院项目时需要）
- 可访问的兼容 OpenAI API 的模型服务；具体项目可能还需要额外服务或 API Key

## 快速开始

### Stella 终端聊天应用

在仓库根目录运行以下命令安装依赖并启动：

```powershell
python -m pip install -r Agent/Stella/tui/requirements.txt
python -m Agent.Stella.tui
```

Stella 从启动工作目录读取配置。首次使用可复制示例配置，再按需填写模型服务信息：

```powershell
Copy-Item Agent/Stella/core/config.example.ini Agent/Stella/core/config.ini
```

### Agent 基础练习

在对应练习目录安装 `openai` 套件，填写该目录的 `config.ini` 后执行脚本：

```powershell
python -m pip install openai
Set-Location Agent/Practice01
python chat.py
```

Practice02 可在 `Agent/Practice02` 目录执行 `chat.py`、`chat2.py` 或 `chat3.py`，各版本功能逐步扩展。

### AnythingLLM MCP 服务

安装依赖，并按 [`服务说明`](AnythingLLM_MCP/README.md) 配置环境变量后运行：

```powershell
python -m pip install -r AnythingLLM_MCP/requirements.txt
python AnythingLLM_MCP/server.py
```

## 项目说明

- Stella 将会话与工具等业务逻辑放在 `core`，将终端交互放在 `tui`。
- Practice02 展示了从基本工具调用到本地文件操作工具的迭代过程。
- AnythingLLM MCP 服务提供工作区问答、信息读取和文档检索等工具。
- 宠物医院项目的运行、接口和构建方式请参阅其独立 README。

## 提交前检查

仓库中的 `config.ini` 可能包含 API Key 或其他本地配置。上传前请检查所有配置、日志、数据库和个人信息文件；只提交示例配置或已脱敏内容。当前 `.gitignore` 未覆盖所有 `config.ini`，不能仅凭忽略规则判断文件安全。

在 PowerShell 中检查待提交文件：

```powershell
git status --short
git diff --cached --name-only
```

确认没有真实密钥、私有数据或不需要提交的本地生成文件后，再推送到 GitHub。如果密钥曾经提交到 Git 历史，仅删除当前文件并不足够，应立即在对应服务中撤销并重新生成密钥。

