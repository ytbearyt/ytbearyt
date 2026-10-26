"# LLM 实践工作区

个人 LLM 应用学习与实践工作区，核心项目为 `Agent/Stella`，采用 core（业务核心）与 tui（终端界面）分离的分层架构。

## 目录结构

```text
LLM/
├── Agent/
│   ├── Practice01/
│   ├── Practice02/
│   └── Stella/
│       ├── core/
│       ├── tui/
│       └── README.md
├── AnythingLLM_MCP/
├── AnythingLLMServer/
└── petHospital_MCP/
```

## 核心项目：Agent/Stella

### 架构

```text
Stella/
├── core/
│   ├── chat.py        # 会话与 LLM 流式交互
│   ├── config.py      # 配置读取
│   ├── events.py      # 聊天事件协议
│   ├── tools.py       # 工具 schema 与工具分发
│   └── tests/         # 核心模块测试
└── tui/
    ├── __main__.py    # 呈现终端界面入口
    ├── app.py         # Textual 界面实现
    ├── README.md      # TUI 说明
    └── requirements.txt
```

Stella 将模型会话、工具调用和终端界面分离：`core` 负责业务逻辑，`tui` 负责交互展示。

### 启动

```powershell
python -m pip install -r Agent/Stella/tui/requirements.txt
python -m Agent.Stella.tui
```

## 快速使用

复制配置模板并填写模型及搜索服务参数：

```powershell
Copy-Item Agent/Stella/core/config.example.ini Agent/Stella/core/config.ini
```

不要提交真实 API Key。

### Stella 功能

- 多轮对话与流式响应
- `searchWeb`：调用千帆智能搜索获取实时信息与参考来源
- `fetchWeb`：抓取网页并提取主要正文为 Markdown
- `RunCli`：以当前用户权限执行本地命令行程序
- 本地文件与目录操作工具

## 环境要求

- Windows 或其他支持 Python 的操作系统
- Python 3.10 及以上
- 可用的 LLM API Key
- 千帆搜索 API Key（使用联网搜索时）
- 本机已安装 `curl`

安装依赖：

```powershell
python -m pip install -r Agent/Stella/tui/requirements.txt
```

## 安全提交说明

提交作业前，请确认以下敏感文件未被 Git 跟踪或提交：

- `Agent/Stella/core/config.ini`
- 任何包含真实 API Key 的配置或日志文件

可通过以下命令检查：

```powershell
git status
git check-ignore -v Agent/Stella/core/config.ini
```

