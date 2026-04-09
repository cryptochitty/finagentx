"""
FinAgentX – BaseAgent
All agents inherit from here. Provides LLM abstraction, logging, and memory context.
"""
import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.config import LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL

logger = logging.getLogger("finagentx.agents")


class LLMClient:
    """
    Thin wrapper around multiple LLM providers.
    Falls back to mock responses if provider is 'mock' or API key is missing.
    """

    def __init__(self):
        self.provider = LLM_PROVIDER
        self.model    = LLM_MODEL

    def complete(self, system: str, user: str) -> str:
        if self.provider == "mock" or not LLM_API_KEY:
            return self._mock_response(user)

        if self.provider == "gemini":
            return self._gemini(system, user)

        if self.provider == "openai":
            return self._openai(system, user)

        if self.provider == "ollama":
            return self._ollama(system, user)

        return self._mock_response(user)

    # ── Provider implementations ──────────────────────────────────────────────

    def _gemini(self, system: str, user: str) -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=LLM_API_KEY)
            m = genai.GenerativeModel(self.model, system_instruction=system)
            resp = m.generate_content(user)
            return resp.text
        except Exception as e:
            logger.warning(f"Gemini failed: {e} – using mock")
            return self._mock_response(user)

    def _openai(self, system: str, user: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL or None)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user",   "content": user}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning(f"OpenAI failed: {e} – using mock")
            return self._mock_response(user)

    def _ollama(self, system: str, user: str) -> str:
        try:
            import requests
            base = LLM_BASE_URL or "http://localhost:11434"
            resp = requests.post(
                f"{base}/api/chat",
                json={"model": self.model, "stream": False,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user",   "content": user}]},
                timeout=60,
            )
            return resp.json()["message"]["content"]
        except Exception as e:
            logger.warning(f"Ollama failed: {e} – using mock")
            return self._mock_response(user)

    def _mock_response(self, prompt: str) -> str:
        """Rule-based mock so the demo always works without real API keys."""
        return (
            "Based on current market analysis, the momentum indicators suggest "
            "a moderate bullish signal. Risk levels are within acceptable parameters. "
            "Recommend proceeding with a conservative position size of 5%."
        )


# ─── Base Agent ───────────────────────────────────────────────────────────────

class BaseAgent:
    """
    Every FinAgentX agent extends BaseAgent.
    - self.llm     → call the LLM
    - self.memory  → list of prior messages (shared context across agents)
    - self.log()   → structured decision logging
    """

    name: str = "BaseAgent"

    def __init__(self, shared_memory: Optional[List[Dict]] = None):
        self.llm    = LLMClient()
        self.memory = shared_memory if shared_memory is not None else []
        self.logger = logging.getLogger(f"finagentx.{self.name.lower()}")

    def log(self, decision_type: str, payload: Any, explanation: str = "") -> Dict:
        """Create a structured decision log entry."""
        entry = {
            "agent":         self.name,
            "decision_type": decision_type,
            "payload":       payload,
            "explanation":   explanation,
            "timestamp":     datetime.utcnow().isoformat(),
        }
        # Append to shared memory so downstream agents can reference it
        self.memory.append(entry)
        self.logger.info(f"[{self.name}] {decision_type}: {explanation[:120]}")
        return entry

    def get_memory_context(self, last_n: int = 5) -> str:
        """Return recent memory as a JSON string for LLM context injection."""
        recent = self.memory[-last_n:] if self.memory else []
        return json.dumps(recent, indent=2, default=str)

    def ask_llm(self, task_prompt: str, system_prompt: Optional[str] = None) -> str:
        system = system_prompt or (
            f"You are the {self.name} in the FinAgentX multi-agent financial system. "
            "Always respond with concise, structured JSON when asked for data. "
            "Be decisive and data-driven."
        )
        # Inject recent memory into every LLM call for cross-agent context
        context = self.get_memory_context()
        full_prompt = f"Recent agent decisions:\n{context}\n\nCurrent task:\n{task_prompt}"
        return self.llm.complete(system, full_prompt)
