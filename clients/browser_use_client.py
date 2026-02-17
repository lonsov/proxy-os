"""Browser Use client wrapper for agentic web search and extraction."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


def _as_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _as_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_as_jsonable(v) for v in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _as_jsonable(model_dump(mode="json"))
        except Exception:
            try:
                return _as_jsonable(model_dump())
            except Exception:
                pass

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _as_jsonable(to_dict())
        except Exception:
            pass

    obj_dict = getattr(value, "__dict__", None)
    if isinstance(obj_dict, dict):
        return _as_jsonable(obj_dict)
    return str(value)


def _extract_json_object(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


@dataclass
class BrowserUseSource:
    name: str = ""
    url: str = ""
    snippet: str = ""
    favicon: str = ""


@dataclass
class BrowserUseSourcedAnswer:
    answer: str
    sources: List[BrowserUseSource]

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": [_as_jsonable(s) for s in self.sources],
        }


class BrowserUseClient:
    """Thin sync wrapper over browser_use.Agent for compatibility."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GOOGLE_API_KEY not found in .env")
        # Browser Use's Google integration reads GOOGLE_API_KEY from env.
        os.environ["GOOGLE_API_KEY"] = key
        self.api_key = key

    async def _run_agent(self, task: str) -> Any:
        from browser_use import Agent, ChatGoogle

        model = os.getenv("BROWSER_USE_GOOGLE_MODEL", "gemini-flash-latest")
        llm = ChatGoogle(model=model)
        agent = Agent(task=task, llm=llm)
        return await agent.run()

    def _run_task(self, task: str) -> Any:
        try:
            return asyncio.run(self._run_agent(task))
        except RuntimeError:
            # Fallback for environments with an active event loop.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._run_agent(task))
            finally:
                loop.close()

    @staticmethod
    def _result_text(result: Any) -> str:
        if isinstance(result, str):
            return result
        final_result = getattr(result, "final_result", None)
        if callable(final_result):
            try:
                out = final_result()
                if isinstance(out, str):
                    return out
                return json.dumps(_as_jsonable(out))
            except Exception:
                pass
        return json.dumps(_as_jsonable(result))

    def search(
        self,
        *,
        query: str,
        depth: str = "standard",
        output_type: str = "searchResults",
        max_results: int = 5,
        structured_output_schema: Optional[str] = None,
        include_inline_citations: bool = False,
        include_images: bool = False,
        include_sources: bool = True,
        **_: Any,
    ) -> Any:
        depth_hint = "very thorough" if depth == "deep" else "quickly"
        if output_type == "structured":
            schema_hint = structured_output_schema or "{}"
            task = (
                f"Search the web {depth_hint} for this query:\n{query}\n\n"
                "Return ONLY valid JSON that matches this JSON schema exactly.\n"
                f"{schema_hint}\n\n"
                f"Do not include markdown. Prefer up to {max_results} entries where relevant."
            )
            raw = self._result_text(self._run_task(task))
            return _extract_json_object(raw) or {"raw": raw}

        if output_type == "sourcedAnswer":
            citation_rule = (
                "Use inline numeric citations like [1], [2] for key claims."
                if include_inline_citations
                else "Citations are optional."
            )
            source_rule = "Include a sources list." if include_sources else "No source list needed."
            task = (
                f"Research this query {depth_hint}:\n{query}\n\n"
                "Return ONLY valid JSON with this exact shape:\n"
                '{"answer":"string","sources":[{"name":"string","url":"string","snippet":"string","favicon":"string"}]}\n'
                f"{citation_rule} {source_rule} Limit to {max_results} sources."
            )
            raw = self._result_text(self._run_task(task))
            parsed = _extract_json_object(raw) or {}
            sources = []
            for s in parsed.get("sources") or []:
                if not isinstance(s, dict):
                    continue
                sources.append(
                    BrowserUseSource(
                        name=str(s.get("name") or ""),
                        url=str(s.get("url") or ""),
                        snippet=str(s.get("snippet") or ""),
                        favicon=str(s.get("favicon") or ""),
                    )
                )
            answer = str(parsed.get("answer") or raw)
            return BrowserUseSourcedAnswer(answer=answer, sources=sources)

        image_rule = "You may include image context if useful." if include_images else "Ignore images."
        task = (
            f"Search the web {depth_hint} for this query:\n{query}\n\n"
            "Return ONLY valid JSON with shape:\n"
            '{"results":[{"title":"string","url":"string","content":"string","source":"string","location":"string","date_posted":"string"}]}\n'
            f"Provide up to {max_results} results. {image_rule}"
        )
        raw = self._result_text(self._run_task(task))
        parsed = _extract_json_object(raw) or {}
        results = parsed.get("results")
        if isinstance(results, list):
            return {"results": results}
        return {"results": [], "raw": raw}


def browser_use_search(
    query: str,
    depth: str = "standard",
    output_type: str = "searchResults",
    max_results: int = 5,
    **kwargs: Any,
) -> Any:
    client = BrowserUseClient()
    return client.search(
        query=query,
        depth=depth,
        output_type=output_type,
        max_results=max_results,
        **kwargs,
    )


__all__ = [
    "BrowserUseClient",
    "BrowserUseSource",
    "BrowserUseSourcedAnswer",
    "browser_use_search",
]
