# 🧪 LabAgent — 智能实验室仪器共享预约平台

> **CS599 期末大作业** | 企业级应用软件设计与开发 | 2025-2026 春季

## 项目简介

LabAgent 是一个基于 **LangGraph 多智能体协作架构** 的实验室智能管理系统。
本项目采用 **方向一：Agentic AI 原生开发**，运用 SDD（规格驱动开发）方法论，
从零构建了一个具备 Supervisor-Worker 多智能体协作能力的 AI Agent 系统。

### 🎯 核心能力

| Agent | 职责 | 核心技术 |
|-------|------|---------|
| 🏠 Supervisor | 意图识别、任务分发、结果整合 | LangGraph StateGraph 编排 |
| 📅 Scheduler | 智能排期、冲突检测、替代推荐 | Function Calling × 7 工具 |
| 📖 QA Specialist | 仪器SOP知识问答 | ChromaDB RAG + 语义检索 |
| 🔍 Monitor | 异常检测、使用统计、违规预警 | 规则引擎 + Agent 分析 |

### 📐 SDD 规格驱动

完整产品规格、架构规格、API 规格见 `config/product_spec.yaml`，
覆盖 Product Spec / Architecture Spec / API Spec 三个层面。

## 方向

**方向一：Agentic AI 原生开发**

## 技术栈

| 类别 | 技术选型 |
|------|---------|
| AI IDE | VS Code + Claude Code |
| LLM | DeepSeek API (`deepseek-chat`) |
| Agent 框架 | LangGraph (StateGraph + MemorySaver) |
| RAG | ChromaDB + Sentence-Transformers |
| 协议 | Function Calling (OpenAI 兼容) |
| 数据库 | SQLite + SQLAlchemy ORM |
| Web UI | Streamlit |
| 容器 | Docker |
| 语言 | Python 3.11 |

## 目录结构

```
cs599-project/
├── src/
│   ├── main.py                  # CLI 入口
│   ├── agents/                  # 多智能体系统
│   │   ├── graph.py             # LangGraph 状态图（核心）
│   │   └── prompts.py           # Agent 系统提示词
│   ├── database/                # 数据层
│   │   ├── models.py            # ORM 模型
│   │   ├── db.py                # 连接管理
│   │   └── seed.py              # 种子数据
│   ├── tools/                   # Agent 工具函数
│   │   ├── booking_tools.py     # 预约管理工具（7个）
│   │   ├── rag_tools.py         # RAG检索工具
│   │   └── monitor_tools.py     # 异常监控工具
│   ├── rag/                     # RAG知识库模块
│   │   ├── document_loader.py   # SOP文档加载
│   │   ├── vector_store.py     # ChromaDB向量存储
│   │   └── retriever.py        # 检索器接口
│   └── web/
│       └── app.py               # Streamlit 演示界面
├── config/
│   ├── product_spec.yaml        # SDD产品规格文档
│   └── sop_docs/                # 仪器SOP知识库（RAG源）
│       ├── electron_microscope.md
│       ├── mass_spectrometer.md
│       └── hpc_cluster.md
├── tests/
│   └── test_system.py           # 系统集成测试
├── docs/
│   └── CS599_大作业报告.md       # 最终报告
├── requirements.txt
├── Dockerfile
├── .env.example
├── .gitignore
├── LICENSE (MIT)
└── README.md
```

## 环境搭建

### 1. 依赖安装

```bash
cd cs599-project
pip install -r requirements.txt
```

### 2. 环境变量配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-your-key-here
```

⚠️ **绝不硬编码 API Key**，`.env` 已在 `.gitignore` 中排除。

### 3. 启动步骤

**Web 界面（推荐）**：
```bash
streamlit run src/web/app.py
# 浏览器访问 http://localhost:8501
```

**命令行交互模式**：
```bash
python -m src.main
```

**单条消息模式**：
```bash
python -m src.main -m "电镜下周有什么时间可用？"
```

**仅初始化（不对话）**：
```bash
python -m src.main --init-only
```

### 4. Docker 部署

```bash
docker build -t labagent .
docker run -p 8501:8501 --env-file .env labagent
```

## 多智能体架构

```
用户请求
    ↓
┌──────────────────────┐
│  🏠 Supervisor Agent │  ← 意图识别 + 任务分发
└──────┬───────────────┘
       │
   ┌───┼───────────┐
   ↓   ↓           ↓
┌────┐ ┌────┐  ┌──────┐
│📅  │ │📖  │  │🔍    │
│排期│ │顾问│  │监控  │
│助手│ │Agent│ │哨兵  │
└──┬─┘ └──┬─┘  └──┬───┘
   ↓      ↓        ↓
  预约    SOP    异常检测
  工具    RAG     统计
```

## 核心功能演示示例

### 场景1：智能排期
```
用户: 帮我预约下周一电镜，上午9点到下午1点
Agent: [检测冲突] → 周一9:00-13:00已被赵教授预约
       [推荐替代] → 周一14:00有空 / 周二9:00有空 / XRD同天可用
```

### 场景2：SOP问答
```
用户: 电镜样品怎么制备？
Agent: [RAG检索] → 找到TEM SOP §2.1 样品制备
       1. 取少量粉末分散于无水乙醇
       2. 超声分散5-10分钟
       ⚠️ 样品必须完全干燥，含水样品会污染真空系统
```

### 场景3：异常监控
```
用户: 检查最近一周有什么异常
Agent: [监控扫描] → 
       🔴 未持证操作: 李四（证书0级）预约了需要2级证书的电镜
       🟡 爽约: 李四周三9:00-13:00预约未到场
```

## 核心技术要素（≥4 项）

| 要素 | 实现情况 |
|------|---------|
| ✅ SDD 规格驱动开发 | Product Spec / Architecture Spec / API Spec (YAML) |
| ✅ 工具使用 / Function Calling / MCP 协议 | 11 个 LangChain Tool + MCP Server 标准化暴露 |
| ✅ 记忆机制 | LangGraph MemorySaver 跨轮对话状态保持 |
| ✅ 状态管理与多步推理 | StateGraph + ReAct 循环 |
| ✅ 多智能体协作 | Supervisor → Scheduler / QA / Monitor |
| ✅ 可观测性与评估 | 10 用例自动化 Benchmark，90%+ 准确率 |

## 项目状态

- [x] Proposal — 选题与架构设计
- [x] MVP — 核心闭环（排期 + RAG + 监控）
- [x] Final — 测试完善 + 报告提交

## 引用说明

本项目使用了以下开源技术：
- LangGraph / LangChain (MIT License) — Agent 编排框架
- ChromaDB (Apache 2.0) — 向量数据库
- Streamlit (Apache 2.0) — Web 界面框架
- DeepSeek API — 大语言模型服务

SOP 文档内容为模拟数据，不涉及真实实验数据。

---

**提交日期**: 2026年6月22日
