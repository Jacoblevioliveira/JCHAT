import os
import requests
import logging
from datetime import date
from openai import OpenAI, OpenAIError
from PySide6.QtCore import QThread, Signal

from .helpers import is_enabled, build_messages
from .feature_flags import FeatureFlag
from .constants import MODEL

log = logging.getLogger(__name__)

def search_web(query: str, k: int = 3) -> list[dict]:
    try:
        api_key = os.getenv("SERPAPI_KEY")
        if not api_key:
            log.warning("SERPAPI_KEY missing; skipping web search.")
            return []

        params = {
            "engine": "google",
            "q": query,
            "num": max(3, k),
            "api_key": api_key,
        }
        
        r = requests.get("https://serpapi.com/search", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        results = []
        for item in (data.get("organic_results") or [])[:k]:
            results.append({
                "title": item.get("title") or "",
                "url": item.get("link") or "",
                "snippet": item.get("snippet") or "",
            })
        return results
    except Exception as e:
        log.warning(f"Web search failed: {e}")
        return []

def make_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment or .env")
    return OpenAI(api_key=api_key)

CLIENT = make_client()

class ChatThread(QThread):
    result_ready = Signal(str)
    error = Signal(str)
    chunk_ready = Signal(str)

    def __init__(
        self,
        history: list[dict],
        prompt: str,
        use_features: bool = True,
        feature_set: dict = None,
        is_option_b: bool = False,
        *,
        force_web_search: bool = False
    ) -> None:
        super().__init__()
        self.history = history
        self.prompt = prompt
        self.use_features = use_features
        self.feature_set = feature_set
        self.is_option_b = is_option_b
        self.force_web_search = force_web_search

    def _handle_streaming(self, messages: list[dict]) -> str:
        full_response = ""
        stream = CLIENT.chat.completions.create(model=MODEL, messages=messages, stream=True)
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                chunk_text = chunk.choices[0].delta.content
                full_response += chunk_text
                self.chunk_ready.emit(chunk_text)
        return full_response

    def run(self) -> None:
        try:
            sources: list[dict] = []

            if self.force_web_search and is_enabled(FeatureFlag.WEB_SEARCH):
                sources = search_web(self.prompt, k=3)

            messages = build_messages(self.history, self.prompt, self.use_features, self.feature_set)
            messages.insert(0, {"role": "system", "content": f"Current date: {date.today().isoformat()}"})

            if sources:
                src_block = "\n".join(
                    f"- {s['title']} — {s['url']}\n  {s['snippet']}"
                    for s in sources if s.get("url")
                ).strip()
                
                messages.insert(0, {
                    "role": "system",
                    "content": (
                        "You were provided recent web snippets and links.\n"
                        "RULES:\n"
                        "1) Prefer facts from SOURCES over memory.\n"
                        "2) If SOURCES conflict, state which source supports which claim.\n"
                        "3) If a claim isn't supported by SOURCES, say you can't confirm.\n"
                        "4) Do not invent citations.\n\n"
                        f"SOURCES:\n{src_block}"
                    )
                })

            if is_enabled(FeatureFlag.STREAMING):
                result = self._handle_streaming(messages)
            else:
                resp = CLIENT.chat.completions.create(model=MODEL, messages=messages)
                result = (resp.choices[0].message.content or "").strip()

            if sources:
                result = "🔎 Web-grounded answer:\n" + result
                result += "\n\nSources:\n" + "\n".join(f"- {s['url']}" for s in sources if s.get("url"))

            self._sources_used = sources
            self.result_ready.emit(result)

        except OpenAIError as e:
            self.error.emit(f"API error: {e}")
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")