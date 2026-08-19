from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass


@dataclass
class CoderModelConfig:
    """
    Coder 模型配置。

    使用 OpenAI compatible 格式调用模型。
    没有 API Key 时默认走 Mock，方便先跑通流程。
    """

    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    model: str = "qwen-plus"
    temperature: float = 0.0
    timeout: int = 60
    use_mock_when_no_api_key: bool = True


class CoderModelClient:
    """
    Coder 模型 Client。
    """

    def __init__(self, config: CoderModelConfig | None = None):
        self.config = config or CoderModelConfig()

        if not self.config.api_key:
            self.config.api_key = os.getenv("DASHSCOPE_API_KEY", "")

    def generate_sql(self, prompt: str) -> str:
        """
        生成 SQL。
        """
        if self.config.api_key:
            return self._call_model(prompt)

        if self.config.use_mock_when_no_api_key:
            return self._mock_generate(prompt)

        raise ValueError("缺少 DASHSCOPE_API_KEY，无法调用 Coder 模型。")

    def _call_model(self, prompt: str) -> str:
        """
        调用 Coder 模型。
        """
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": self.config.temperature,
            "stream": False,
        }

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        request = urllib.request.Request(
            self.config.base_url,
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                body = response.read().decode("utf-8")
                result = json.loads(body)
        except Exception as exc:
            raise RuntimeError(f"调用 Coder 模型失败: {exc}") from exc

        try:
            return result["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            raise RuntimeError(f"解析 Coder 模型返回失败，原始返回：{result}") from exc

    def _mock_generate(self, prompt: str) -> str:
        """
        Mock SQL 生成。

        只用于本地跑通流程。
        真实效果以 Coder 模型输出为准。
        """
        if (
            "trade_summary" in prompt
            and "interest_info" in prompt
            and "total_trade_count" in prompt
            and "interest_rate" in prompt
        ):
            return """SELECT interest_info.interest_rate
FROM trade_summary
JOIN interest_info
  ON trade_summary.user_id = interest_info.user_id
WHERE trade_summary.total_trade_count > 50000;"""

        return "SELECT 1;"

    def clean_sql(self, text: str) -> str:
        """
        清理模型输出，只保留 SQL。

        处理：
        - 去掉 Markdown 代码块
        - 去掉“输出SQL语句：”之类的前缀
        - 提取 SELECT/WITH 开头的 SQL
        """
        text = text.strip()

        text = re.sub(
            r"^```(?:sql)?\s*",
            "",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\s*```$",
            "",
            text,
            flags=re.I,
        )

        text = re.sub(
            r"^(输出SQL语句|SQL语句|SQL)\s*[:：]\s*",
            "",
            text,
            flags=re.I,
        ).strip()

        match = re.search(
            r"((?:SELECT|WITH)\b[\s\S]*?;?)\s*$",
            text,
            flags=re.I,
        )

        if match:
            sql = match.group(1).strip()
        else:
            sql = text

        if sql and not sql.endswith(";"):
            sql += ";"

        return sql
