# AskData Text2SQL Demo

本项目演示从自然语言 Query 到 SQL 生成与执行的端到端流程。

## 核心模块

```text
schema_indexing/      # Schema索引构建，离线阶段
schema_retrieval/     # Schema检索与SchemaGraph构建
cot_planning/         # CoT四元组规划
sql_generation/       # SQL生成
mcp_router/           # MCP路由执行
askdata_pipeline/     # 端到端流程编排
askdata_memory/       # 长短期记忆、个人知识库召回与会话编排
```

## 端到端运行

```bash
python -m askdata_pipeline.end_to_end_demo
```

当前 Demo 会自动创建 SQLite 测试库：

```text
runtime_data/trade_demo.db
```

测试 Query：

```text
查询总交易笔数大于50000的利率是多少
```

## 当前链路

```text
用户Query
  ↓
关键词抽取
  ↓
Schema混合检索 + RRF + Rerank
  ↓
SchemaGraph
  ↓
CoT四元组规划
  ↓
SQL生成
  ↓
MCP路由执行
  ↓
查询结果
```

动态路由会先结合长短期记忆判断用户意图：需要新业务数据时进入上述 Text2SQL 链路；结果解释、指标说明、历史结果追问和业务知识问答进入 `data_qa` 链路，不执行数据库查询。

路由实现位于 `askdata_pipeline/routing.py`，统一编排入口位于 `askdata_pipeline/dynamic_service.py`，对话问答实现位于 `askdata_pipeline/data_qa.py`。

暂不包含结果校验与回调修正。

## 长短期记忆

项目已支持滑动窗口、异步增量摘要、用户主动长期记忆存储，以及可选个人知识库召回。详细设计与调用方式见 [askdata_memory/README.md](askdata_memory/README.md)。

运行长短期记忆端到端 Demo：

```bash
python askdata_pipeline/memory_end_to_end_demo.py
```
