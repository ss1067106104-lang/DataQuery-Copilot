from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from cot_planning import CotPlanner, ThinkingModelClient, ThinkingModelConfig
from mcp_router import MCPRouter, SQLiteMCPExecutor
from schema_retrieval.hybrid_schema_retrieval_service import (
    HybridSchemaRetrievalConfig,
    HybridSchemaRetrievalService,
)
from schema_retrieval.rerank_client import AliyunRerankClient, AliyunRerankConfig
from schema_retrieval.rrf_fusion_client import RRFFusionConfig
from sql_generation import (
    CoderModelClient,
    CoderModelConfig,
    CotStep,
    LocalSchemaStore,
    SqlGenerator,
)

from .demo_data import create_trade_demo_database, get_trade_business_meta
from .local_clients import LocalHashEmbeddingClient, SimpleKeywordExtractor
from .objects import PipelineConfig, PipelineResult, StepExecutionLog


class AskDataText2SQLPipeline:
    """
    AskData Text2SQL 端到端流程。

    当前实现串联：
    1. 创建测试数据库和 Schema 元数据
    2. Schema 检索与 SchemaGraph 构建
    3. CoT 四元组规划
    4. SQL 生成
    5. MCP 路由执行

    暂不包含结果校验与回调修正。
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.keyword_extractor = SimpleKeywordExtractor()

        self.db_path = create_trade_demo_database(self.config.db_path)
        self.business_meta = get_trade_business_meta()

        self.schema_retrieval_service = self._build_schema_retrieval_service()
        self.cot_planner = self._build_cot_planner()
        self.mcp_router = self._build_mcp_router()

    def run(
        self,
        query: str,
        keywords: Optional[List[str]] = None,
        conversation_context: str = "",
    ) -> PipelineResult:
        """
        执行完整 Text2SQL 流程。
        """
        resolved_keywords = keywords or self.keyword_extractor.extract(query)

        contextual_query = query
        if conversation_context.strip():
            contextual_query = (
                f"以下是与当前问题相关的会话记忆：\n{conversation_context}\n\n"
                f"当前用户问题：{query}"
            )

        retrieval_result = self.schema_retrieval_service.retrieve(
            query=contextual_query,
            keywords=resolved_keywords,
        )

        schema_graph = retrieval_result.schema_graph
        schema_context = schema_graph.to_prompt_context()

        cot_result = self.cot_planner.plan(
            user_query=contextual_query,
            schema_graph=schema_graph,
        )

        schema_store = LocalSchemaStore.from_schema_graph(schema_graph)

        sql_generator = SqlGenerator(
            schema_store=schema_store,
            coder_client=CoderModelClient(
                CoderModelConfig(
                    use_mock_when_no_api_key=True,
                )
            ),
        )

        step_logs: List[StepExecutionLog] = []

        for cot_step in cot_result.steps:
            sql_cot_step = CotStep(
                database=cot_step.database,
                processing_objects=cot_step.processing_objects,
                operation_instruction=cot_step.operation_instruction,
                output_target=cot_step.output_target,
            )

            local_schema = schema_store.extract_local_schema(sql_cot_step)
            sql_result = sql_generator.generate(sql_cot_step)

            execution_request = sql_result.to_execution_request()
            execution_result = self.mcp_router.execute(execution_request)

            step_logs.append(
                StepExecutionLog(
                    database=sql_cot_step.database,
                    cot_step=sql_cot_step,
                    local_schema=local_schema.to_prompt_context(),
                    sql=sql_result.sql,
                    execution_request=execution_request,
                    execution_result=execution_result.to_dict(),
                )
            )

        return PipelineResult(
            query=query,
            keywords=resolved_keywords,
            schema_context=schema_context,
            cot_output=cot_result.raw_output,
            step_logs=step_logs,
        )

    def _build_schema_retrieval_service(self) -> HybridSchemaRetrievalService:
        """
        构建 Schema 检索服务。
        """
        embedding_client = LocalHashEmbeddingClient(dimensions=1024)

        rerank_client = AliyunRerankClient(
            AliyunRerankConfig(
                api_key="",
                workspace_id="",
                model="qwen-rerank",
            )
        )

        return HybridSchemaRetrievalService.from_sqlite(
            db_path=self.db_path,
            database_name=self.config.database_name,
            business_meta=self.business_meta,
            embedding_client=embedding_client,
            rerank_client=rerank_client,
            keyword_extractor=None,
            config=HybridSchemaRetrievalConfig(
                per_keyword_top_k=20,
                include_join_columns=True,
                rrf_config=RRFFusionConfig(
                    rrf_k=60,
                    truncate_multiplier=6,
                    min_fused_top_k=10,
                    max_fused_top_k=50,
                    final_top_k=20,
                    route_weights={
                        "keyword": 1.0,
                        "vector": 1.0,
                    },
                ),
                rerank_top_multiplier=2,
                rerank_min_top_n=2,
                rerank_max_top_n=20,
            ),
            sample_size=self.config.sample_size,
        )

    def _build_cot_planner(self) -> CotPlanner:
        """
        构建 CoT 规划器。
        """
        return CotPlanner(
            thinking_client=ThinkingModelClient(
                ThinkingModelConfig(
                    use_mock_when_no_api_key=True,
                    temperature=0.0,
                )
            )
        )

    def _build_mcp_router(self) -> MCPRouter:
        """
        构建 MCP 路由器。
        """
        router = MCPRouter()

        router.register_executor(
            database=self.config.database_name,
            executor=SQLiteMCPExecutor(
                database=self.config.database_name,
                db_path=self.db_path,
                readonly=True,
            ),
        )

        return router
