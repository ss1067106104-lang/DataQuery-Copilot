from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Iterator


@dataclass
class ThinkingModelConfig:
    """
    思考模型配置。

    这里使用 OpenAI compatible 格式调用模型。
    没有 API Key 时默认走 Mock，方便先跑通流程。
    """

    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    model: str = "qwen-plus"
    temperature: float = 0.0
    timeout: int = 60
    use_mock_when_no_api_key: bool = True
    mock_stream_delay: float = 0.02


class ThinkingModelClient:
    """
    思考模型 Client。

    用于将用户 Query 和 Schema 图转换为结构化 CoT 规划结果。
    支持普通输出和流式输出。
    """

    def __init__(self, config: ThinkingModelConfig | None = None):
        self.config = config or ThinkingModelConfig()

        if not self.config.api_key:
            self.config.api_key = os.getenv("DASHSCOPE_API_KEY", "")

    def generate(self, prompt: str) -> str:
        """
        非流式生成规划结果。
        """
        if self.config.api_key:
            return self._call_model(prompt)

        if self.config.use_mock_when_no_api_key:
            return self._mock_generate(prompt)

        raise ValueError("缺少 DASHSCOPE_API_KEY，无法调用思考模型。")

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """
        流式生成规划结果。

        返回一个迭代器，每次 yield 一小段文本。
        Demo 中可以边生成边 print。
        """
        if self.config.api_key:
            yield from self._call_model_stream(prompt)
            return

        if self.config.use_mock_when_no_api_key:
            yield from self._mock_generate_stream(prompt)
            return

        raise ValueError("缺少 DASHSCOPE_API_KEY，无法调用思考模型。")

    def _call_model(self, prompt: str) -> str:
        """
        调用大模型，非流式。
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

        result = self._post_json(payload)

        try:
            return result["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            raise RuntimeError(f"解析思考模型返回失败，原始返回：{result}") from exc

    def _call_model_stream(self, prompt: str) -> Iterator[str]:
        """
        调用大模型，流式。

        兼容 OpenAI SSE 格式：
            data: {"choices":[{"delta":{"content":"..."}}]}
            data: [DONE]
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
            "stream": True,
        }

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            "Accept": "text/event-stream",
        }

        request = urllib.request.Request(
            self.config.base_url,
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()

                    if not line:
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_text = line[len("data:"):].strip()

                    if data_text == "[DONE]":
                        break

                    try:
                        event = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue

                    delta = event.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")

                    if content:
                        yield content

        except Exception as exc:
            raise RuntimeError(f"流式调用思考模型失败: {exc}") from exc

    def _post_json(self, payload: dict) -> dict:
        """
        发送 JSON 请求。
        """
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
                return json.loads(body)
        except Exception as exc:
            raise RuntimeError(f"调用思考模型失败: {exc}") from exc

    def _mock_generate(self, prompt: str) -> str:
        """
        Mock 规划结果。
        """
        if (
            "total_trade_count" in prompt
            and "interest_rate" in prompt
            and "trade_summary.user_id" in prompt
            and "interest_info.user_id" in prompt
        ):
            return """步骤1：
(
  数据库: trade_db,
  处理对象: trade_summary.total_trade_count，interest_info.interest_rate，trade_summary.user_id，interest_info.user_id，trade_summary.user_id ↔ interest_info.user_id,
  操作指令: 先在trade_summary表中筛选total_trade_count大于50000的记录，并获取对应user_id；再基于user_id关联interest_info表；最后获取对应的interest_rate,
  输出目标: interest_info.interest_rate
)"""

        return """步骤1：
(
  数据库: 缺失,
  处理对象: Schema中未找到足够的表、字段或表关联关系,
  操作指令: 先检查用户Query涉及的筛选字段、输出字段和表关联关系；再发现当前Schema无法完整支撑该查询；最后返回缺失信息说明,
  输出目标: 缺失，无法生成明确输出目标
)"""

    def _mock_generate_stream(self, prompt: str) -> Iterator[str]:
        """
        Mock 流式输出。

        为了让 Demo 看起来像真实流式输出，这里按字符逐步 yield。
        """
        text = self._mock_generate(prompt)

        for char in text:
            yield char
            time.sleep(self.config.mock_stream_delay)
