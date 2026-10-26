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
" 
