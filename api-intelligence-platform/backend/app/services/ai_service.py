"""AI service supporting dual backend: OpenAI and Ollama.

Provides embedding, chat completion, and structured extraction helpers.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# System prompts
_SYSTEM_PROMPT = """You are an expert API analyst and payment systems architect.
You deeply understand REST APIs, OpenAPI specifications, payment flows (UPI, NPCI, PSP, bank APIs),
security standards, and API governance best practices.
Always respond with precise, structured, and actionable information.
When asked to extract structured data, respond ONLY with valid JSON."""

_EXTRACTION_SYSTEM = """You are a precise data extraction AI.
Extract structured information from API specification text.
Always respond with valid JSON only — no markdown, no explanation, no prose.
If a field cannot be determined, use null."""


class AIService:
    """Unified AI service for embedding and chat across OpenAI and Ollama backends."""

    def __init__(self) -> None:
        self.backend = settings.AI_BACKEND.lower()
        self._openai_client: Any = None
        self._http_client: Optional[httpx.AsyncClient] = None

        if self.backend == "openai":
            self._init_openai()
        else:
            self._init_ollama()

        logger.info("AIService initialised", backend=self.backend)

    def _init_openai(self) -> None:
        """Initialise the OpenAI async client."""
        try:
            from openai import AsyncOpenAI  # type: ignore[import]

            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        except ImportError as exc:
            raise RuntimeError("openai package not installed") from exc

    def _init_ollama(self) -> None:
        """Initialise the httpx client for Ollama."""
        self._http_client = httpx.AsyncClient(
            base_url=settings.OLLAMA_BASE_URL,
            timeout=httpx.Timeout(300.0, connect=10.0),
        )

    async def close(self) -> None:
        """Release resources (httpx client for Ollama)."""
        if self._http_client:
            await self._http_client.aclose()

    # ---------------------------------------------------------------------- #
    # Embeddings
    # ---------------------------------------------------------------------- #

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors (one per input text).
        """
        if not texts:
            return []

        if self.backend == "openai":
            return await self._openai_embed(texts)
        return await self._ollama_embed(texts)

    async def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed using OpenAI text-embedding API."""
        # Batch in groups of 100 to stay within API limits
        embeddings: list[list[float]] = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._openai_client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=batch,
            )
            embeddings.extend([item.embedding for item in response.data])
        return embeddings

    async def _ollama_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed using Ollama /api/embeddings endpoint (one at a time)."""
        embeddings: list[list[float]] = []
        for text in texts:
            response = await self._http_client.post(
                "/api/embeddings",
                json={"model": settings.OLLAMA_EMBEDDING_MODEL, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data.get("embedding", []))
        return embeddings

    # ---------------------------------------------------------------------- #
    # Chat completion
    # ---------------------------------------------------------------------- #

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Get a chat completion from the configured AI backend.

        Args:
            messages: List of {'role': str, 'content': str} dicts.
            system_prompt: Optional system message prepended to messages.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the completion.

        Returns:
            The assistant's response text.
        """
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        if self.backend == "openai":
            return await self._openai_chat(full_messages, temperature, max_tokens)
        return await self._ollama_chat(full_messages, temperature)

    async def _openai_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Chat via OpenAI Chat Completions API."""
        response = await self._openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def _ollama_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> str:
        """Chat via Ollama /api/chat endpoint."""
        response = await self._http_client.post(
            "/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    # ---------------------------------------------------------------------- #
    # Structured extraction helpers
    # ---------------------------------------------------------------------- #

    async def extract_apis_from_text(self, text: str) -> list[dict[str, Any]]:
        """Extract API endpoint definitions from arbitrary text.

        Returns:
            List of dicts with keys: path, method, description, parameters,
            request_schema, response_schema, auth_method, tags, risk_level.
        """
        prompt = f"""Extract all API endpoints from the following text.
Return a JSON array where each item has:
- path: string (e.g. "/api/v1/payments")
- method: string (GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)
- description: string or null
- summary: string or null
- parameters: array of {{name, in, required, description}} or []
- request_schema: object or null
- response_schema: object or null
- auth_method: string or null (e.g. "Bearer", "API Key", "OAuth2")
- tags: array of strings
- risk_level: "low"|"medium"|"high"|"critical"
- is_deprecated: boolean

TEXT:
{text[:8000]}

JSON array:"""

        raw = await self.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_EXTRACTION_SYSTEM,
            temperature=0.0,
        )
        return self._parse_json_list(raw, default=[])

    async def extract_flows_from_text(self, text: str) -> list[dict[str, Any]]:
        """Extract business/payment flows from text.

        Returns:
            List of dicts with keys: name, type, description, steps, mermaid_diagram.
        """
        prompt = f"""Extract all business flows or payment flows from the following text.
Return a JSON array where each item has:
- name: string
- type: "direct_pay"|"collect_pay"|"balance_enquiry"|"mandate"|"refund"|"authentication"|"notification"|"other"
- description: string
- steps: array of {{step_number, actor, action, description}}
- mermaid_diagram: string (a valid Mermaid sequenceDiagram) or null
- participants: array of strings (e.g. ["customer", "merchant", "PSP", "bank"])

TEXT:
{text[:8000]}

JSON array:"""

        raw = await self.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_EXTRACTION_SYSTEM,
            temperature=0.0,
        )
        return self._parse_json_list(raw, default=[])

    async def extract_entities_from_text(self, text: str) -> list[dict[str, Any]]:
        """Extract architecture entities from text.

        Returns:
            List of dicts with keys: name, entity_type, properties.
        """
        prompt = f"""Extract all architectural entities from the following API specification text.
Return a JSON array where each item has:
- name: string
- entity_type: "psp"|"bank"|"npci"|"switch"|"merchant"|"customer"|"gateway"|"regulator"|"other"
- properties: object with relevant properties (e.g. {{role, protocols, integrations}})
- description: string or null

TEXT:
{text[:8000]}

JSON array:"""

        raw = await self.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_EXTRACTION_SYSTEM,
            temperature=0.0,
        )
        return self._parse_json_list(raw, default=[])

    async def extract_security_rules(self, text: str) -> list[dict[str, Any]]:
        """Extract security findings and rules from text.

        Returns:
            List of dicts with keys: severity, category, title, description,
            recommendation, affected_endpoints.
        """
        prompt = f"""Analyse the following API specification for security issues.
Return a JSON array of security findings where each item has:
- severity: "critical"|"high"|"medium"|"low"|"info"
- category: string (e.g. "Authentication", "Authorization", "Injection", "Encryption", "Rate Limiting")
- title: string (concise finding title)
- description: string (detailed description of the issue)
- recommendation: string (actionable remediation)
- affected_endpoints: array of strings (endpoint paths)

TEXT:
{text[:8000]}

JSON array:"""

        raw = await self.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_EXTRACTION_SYSTEM,
            temperature=0.0,
        )
        return self._parse_json_list(raw, default=[])

    async def generate_impact_analysis(
        self,
        change_desc: str,
        context: str,
    ) -> dict[str, Any]:
        """Generate an AI-driven impact analysis narrative.

        Args:
            change_desc: Human-readable description of the proposed change.
            context: Relevant API and dependency context (from RAG search).

        Returns:
            Dict with keys: analysis, risk_factors, recommendations,
            security_implications, estimated_risk_score (0-100).
        """
        prompt = f"""You are an API change impact analyst. Analyse the following proposed change
and its surrounding context, then provide a detailed impact assessment.

PROPOSED CHANGE:
{change_desc}

CONTEXT (relevant API definitions and dependencies):
{context[:6000]}

Return a JSON object with:
- analysis: string (detailed narrative analysis, 2-4 paragraphs)
- risk_factors: array of strings (specific risk factors identified)
- recommendations: array of strings (concrete remediation steps)
- security_implications: array of strings (security-related concerns)
- estimated_risk_score: integer 0-100 (0=no risk, 100=critical)
- breaking_change: boolean
- rollback_complexity: "low"|"medium"|"high"

JSON:"""

        raw = await self.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.1,
        )
        return self._parse_json_object(
            raw,
            default={
                "analysis": raw,
                "risk_factors": [],
                "recommendations": [],
                "security_implications": [],
                "estimated_risk_score": 50,
                "breaking_change": False,
                "rollback_complexity": "medium",
            },
        )

    async def generate_governance_report(
        self,
        apis: list[dict[str, Any]],
        rules: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate a governance compliance report using AI reasoning.

        Args:
            apis: List of API endpoint dicts.
            rules: List of governance rule dicts to evaluate.

        Returns:
            Dict with overall_score, rule_results, recommendations, summary.
        """
        apis_summary = json.dumps(apis[:20], indent=2)[:4000]
        rules_text = json.dumps(rules, indent=2)

        prompt = f"""Evaluate the following API endpoints against the governance rules.

API ENDPOINTS:
{apis_summary}

GOVERNANCE RULES TO CHECK:
{rules_text}

Return a JSON object with:
- rule_results: array of {{rule_id, passed, score (0-100), details, affected_endpoints}}
- overall_score: float 0-100
- summary: string
- recommendations: array of strings

JSON:"""

        raw = await self.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_EXTRACTION_SYSTEM,
            temperature=0.0,
        )
        return self._parse_json_object(
            raw,
            default={
                "rule_results": [],
                "overall_score": 0.0,
                "summary": "Governance analysis could not be completed.",
                "recommendations": [],
            },
        )

    async def generate_reuse_recommendations(
        self,
        new_api_desc: str,
        existing_apis: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Recommend existing APIs to reuse instead of building a new one.

        Args:
            new_api_desc: Description of the new API being planned.
            existing_apis: List of existing API endpoint dicts.

        Returns:
            List of dicts: {endpoint_id, path, method, similarity_score, rationale}.
        """
        existing_summary = json.dumps(existing_apis[:30], indent=2)[:5000]

        prompt = f"""A developer wants to build a new API with this description:
"{new_api_desc}"

Existing APIs in the catalog:
{existing_summary}

Identify existing APIs that could be reused or extended instead.
Return a JSON array where each item has:
- endpoint_id: string (from the existing API)
- path: string
- method: string
- similarity_score: float 0.0-1.0
- rationale: string (why this API satisfies the need)
- gaps: array of strings (what is missing compared to the new requirement)
- recommendation: "full_reuse"|"extend"|"fork"|"build_new"

JSON array:"""

        raw = await self.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_EXTRACTION_SYSTEM,
            temperature=0.0,
        )
        return self._parse_json_list(raw, default=[])

    async def answer_with_context(
        self,
        question: str,
        context: str,
        conversation_history: list[dict[str, str]],
    ) -> str:
        """Answer a user question using RAG context and conversation history.

        Args:
            question: The user's current question.
            context: Retrieved document chunks as context.
            conversation_history: Prior messages in the conversation.

        Returns:
            The assistant's answer string.
        """
        system = (
            _SYSTEM_PROMPT
            + "\n\nUse ONLY the provided context to answer questions. "
            "If the context does not contain enough information, say so clearly. "
            "Cite specific API endpoints, flows, or sections when relevant."
        )

        context_msg = f"""CONTEXT FROM API KNOWLEDGE BASE:
---
{context}
---

Based on the above context, answer the following question."""

        messages = list(conversation_history)
        messages.append({"role": "user", "content": f"{context_msg}\n\nQUESTION: {question}"})

        return await self.chat_completion(messages, system_prompt=system, temperature=0.1)

    # ---------------------------------------------------------------------- #
    # Parsing helpers
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _parse_json_list(text: str, default: list) -> list:
        """Extract and parse a JSON array from LLM output."""
        text = text.strip()
        # Strip markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        text = text.strip()

        # Find first '[' and last ']'
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            logger.warning("No JSON array found in LLM response", preview=text[:200])
            return default

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            logger.warning("JSON array parse failed", error=str(exc), preview=text[:200])
            return default

    @staticmethod
    def _parse_json_object(text: str, default: dict) -> dict:
        """Extract and parse a JSON object from LLM output."""
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        text = text.strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("No JSON object found in LLM response", preview=text[:200])
            return default

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            logger.warning("JSON object parse failed", error=str(exc), preview=text[:200])
            return default
