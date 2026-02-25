import os
import json
from typing import Any, Dict, List, Optional

import requests
from libs.config import get_setting


class LLMError(RuntimeError):
    pass


class OpenAICompatLLM:
    def __init__(self) -> None:
        self.base_url = str(get_setting("llm.base_url", os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))).rstrip("/")
        self.api_key = str(get_setting("llm.api_key", os.getenv("LLM_API_KEY", "")))
        self.model = str(get_setting("llm.model", os.getenv("LLM_MODEL", "gpt-4o-mini")))
        self.timeout_s = float(get_setting("llm.timeout_s", os.getenv("LLM_TIMEOUT_S", "12")))

    def enabled(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        if not self.enabled():
            raise LLMError("LLM_API_KEY is not set")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
        except Exception as e:
            raise LLMError(f"request failed: {type(e).__name__}: {e}") from e

        if r.status_code != 200:
            raise LLMError(f"http {r.status_code}: {r.text[:200]}")

        try:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            obj = json.loads(content)
            if not isinstance(obj, dict):
                raise LLMError("model returned non-object json")
            return obj
        except Exception as e:
            raise LLMError(f"invalid model response: {type(e).__name__}: {e}") from e


def build_planner_messages(text: str, speaker: Optional[str], language: Optional[str]) -> List[Dict[str, str]]:
    speaker = (speaker or "unknown").strip().lower()
    language = (language or "zh-CN").strip()
    system = (
        "你是智能座舱 Agent 的规划器。"
        "输出必须是 JSON 对象，且只能是两种之一："
        "1) {\"type\":\"tool_call\",\"tool_name\":\"vehicle.control|nav.poi|nav.route\","
        "\"arguments\":{...},\"requires_confirmation\":false}"
        "2) {\"type\":\"message\",\"message\":{\"text\":\"...\",\"output_modality\":\"voice\",\"should_tts\":true}}。"
        "不要输出 markdown。"
        "如果用户是闲聊、寒暄、咨询，直接返回 message。"
        "如果是车控需求，尽量映射 vehicle.control。"
        "如果是找地点，返回 nav.poi；如果是去某地/规划路线，返回 nav.route。"
        "车窗 position 取值: FL/FR/RL/RR。空调温度 16-30。"
        "vehicle.control arguments 结构: {\"command\":...,\"args\":...}。"
    )
    user = (
        f"speaker={speaker}\n"
        f"language={language}\n"
        f"text={text}\n"
        "请按要求输出 JSON。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
