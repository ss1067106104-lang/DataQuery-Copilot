from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class PipelineConfig:
    """端到端流程配置。"""

    database_name: str = "trade_db"
    db_path: str | Path = "runtime_data/trade_demo.db"
    sample_size: int = 5


@dataclass
class StepExecutionLog:
    """单个 CoT 步骤执行日志。"""

    database: str
    cot_step: object
    local_schema: str
    sql: str
    execution_request: Dict[str, str]
    execution_result: Dict[str, Any]


@dataclass
class PipelineResult:
    """端到端流程结果。"""

    query: str
    keywords: List[str]
    schema_context: str
    cot_output: str
    step_logs: List[StepExecutionLog] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "query": self.query,
            "keywords": self.keywords,
            "schema_context": self.schema_context,
            "cot_output": self.cot_output,
            "step_logs": [
                {
                    "database": log.database,
                    "sql": log.sql,
                    "execution_request": log.execution_request,
                    "execution_result": log.execution_result,
                }
                for log in self.step_logs
            ],
        }
