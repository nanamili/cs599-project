# LabAgent 架构说明

## 系统架构

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Streamlit   │────▶│  LangGraph       │────▶│  Data Layer  │
│  Web UI      │     │  Multi-Agent     │     │              │
│              │     │                  │     │  SQLite      │
│  · 聊天界面   │     │  Supervisor      │     │  ChromaDB    │
│  · 预约日历   │     │    ├─ Scheduler  │     │  SOP Docs    │
│  · 监控面板   │     │    ├─ QA (RAG)   │     │              │
│  · 知识库     │     │    └─ Monitor    │     │              │
└──────────────┘     └─────────────────┘     └──────────────┘
```

## 技术栈

| 层 | 技术 |
|:--|:--|
| UI | Streamlit 1.58 |
| Agent 框架 | LangGraph (StateGraph + MemorySaver) |
| LLM | DeepSeek-Chat (OpenAI 兼容 API) |
| RAG | ChromaDB + Sentence-Transformers |
| 协议 | MCP (Model Context Protocol), Function Calling |
| 数据库 | SQLite + SQLAlchemy ORM |
| 部署 | Docker, Streamlit Cloud |

## 核心模块

### `src/agents/`
多智能体编排核心。Supervisor 负责意图分类和任务分发，Scheduler/QA/Monitor 是三个独立子图（各自 ReAct 循环），通过 MCP 协议动态发现工具。

### `src/tools/`
11 个 Function Calling 工具，覆盖预约管理、RAG 检索、异常监控。

### `src/rag/`
SOP 知识库：文档加载 → 分块 → Sentence-Transformer 嵌入 → ChromaDB 索引 → 语义检索。

### `src/mcp/`
MCP Server（12 工具标准化暴露）+ MCP Client（运行时发现工具并转为 LangChain Tool）。

### `src/database/`
SQLite 数据层：仪器、用户、预约记录的 ORM 模型和种子数据。

### `src/web/`
Streamlit 前端：AI 助手对话、预约日历、监控中心、知识库浏览器。

## 数据流

```
用户输入 → Supervisor(意图分类)
              ├─ Scheduler Agent → Function Calling → SQLite
              ├─ QA Agent → RAG → ChromaDB → LLM 合成
              └─ Monitor Agent → 规则引擎 → SQLite → 报告
         → Supervisor 整合 → 用户
```
