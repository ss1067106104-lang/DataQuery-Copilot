# dataquery\_pipeline

端到端 Text2SQL Demo。

## 目录结构

```text
askdata\_pipeline/
├── \_\_init\_\_.py
├── demo\_data.py             # 测试数据库创建与业务Schema元数据
├── create\_demo\_db.py        # 单独创建SQLite测试库
├── sql\_execution\_demo.py    # 最小MCP SQL执行Demo
├── local\_clients.py         # 本地Mock关键词抽取和Embedding
├── objects.py               # Pipeline数据结构
├── text2sql\_pipeline.py     # 端到端流程编排
└── end\_to\_end\_demo.py       # 完整Text2SQL Demo
```

## 1\. 创建测试数据库

```bash
python -m askdata\_pipeline.create\_demo\_db
```

会生成：

```text
runtime\_data/trade\_demo.db
```

测试数据 SQL 在：

```text
sql/create\_trade\_demo.sql
```

## 2\. 只测试SQL执行环境

```bash
python -m askdata\_pipeline.sql\_execution\_demo
```

这个 Demo 不走大模型，只验证 MCP 路由和 SQLite 执行。

## 3\. 运行端到端流程

```bash
python -m askdata\_pipeline.end\_to\_end\_demo
```

## 4\. 运行动态路由 + 长短期记忆 Demo

```bash
python askdata\_pipeline/memory\_end\_to\_end\_demo.py
```

统一入口为 `DynamicAskDataService`：

* `database\_query`：进入 Schema 检索、CoT、SQL 生成和数据库执行；
* `data\_qa`：用于结果解释、指标说明、历史结果追问、数据分析和业务知识问答，不执行 SQL；
* 路由前先读取短期上下文，并按用户开关决定是否召回长期记忆；
* 配置模型 API Key 时优先使用模型分类，无模型或模型输出异常时使用规则兜底；
* 路由结论会随助手消息写入记忆元信息。

示例：

```python
from askdata\_memory import ConversationMemoryService
from askdata\_pipeline import AskDataText2SQLPipeline, DynamicAskDataService

memory = ConversationMemoryService()
service = DynamicAskDataService(AskDataText2SQLPipeline(), memory)

response = service.run(
    user\_id="user-001",
    session\_id="session-001",
    query="查询总交易笔数大于50000的利率",
)

print(response.decision.route.value)
print(response.decision.reason)
print(response.queried\_database)
print(response.answer)
```

单独运行路由测试：

```bash
python tests/test\_routing.py
```

## 4\. 运行带长短期记忆的端到端流程

bash run\_memory.sh

