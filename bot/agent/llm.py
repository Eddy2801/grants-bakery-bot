"""
LLM agent — OpenRouter (Google Gemini Flash) via OpenAI-compatible API.
"""
import json
import logging

import httpx

from bot.config import config
from bot.agent.prompts import get_system_prompt
from bot.agent.tools import TOOLS, ToolExecutor, to_openai_tools
from bot.redis_client import get_conversation, append_message

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENAI_TOOLS = None


def _get_tools():
    global _OPENAI_TOOLS
    if _OPENAI_TOOLS is None:
        _OPENAI_TOOLS = to_openai_tools(TOOLS)
    return _OPENAI_TOOLS


async def run_agent(
    telegram_id: int,
    user_id: int,
    user_message: str,
    intent: str,
    lang: str,
) -> tuple[str, dict]:
    """
    Run one agentic turn: user_message → LLM (with tools) → response text.

    Returns:
        (response_text, pending_actions)
    """
    system = get_system_prompt(intent, lang)

    # Inject RAG context for question-type intents
    if intent in ("PRODUCT_QUESTION", "HELP", "OTHER"):
        from bot.knowledge import search_knowledge, format_context
        chunks = await search_knowledge(user_message)
        if chunks:
            rag_block = f"\n\n## Relevant knowledge\n{format_context(chunks)}"
            system = system + rag_block

    history = await get_conversation(telegram_id)
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_message}]

    executor = ToolExecutor(telegram_id=telegram_id, user_id=user_id, lang=lang)
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://grantsbakery.lv",
        "X-Title": "Grants Bakery Bot",
    }

    message = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _round in range(5):
            payload = {
                "model": config.LLM_MODEL,
                "messages": messages,
                "tools": _get_tools(),
                "tool_choice": "auto",
                "max_tokens": 1024,
            }

            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason", "stop")

            logger.debug("LLM finish_reason=%s", finish_reason)

            tool_calls = message.get("tool_calls") or []

            if finish_reason in ("stop", "end_turn") or not tool_calls:
                text = message.get("content") or ""
                await append_message(telegram_id, "user", user_message)
                await append_message(telegram_id, "assistant", text)
                return text, {
                    "pending_order": executor._pending_order or None,
                    "pending_subscription": executor._pending_subscription or None,
                }

            # Execute tool calls
            messages.append(message)
            for tc in tool_calls:
                fn = tc["function"]
                try:
                    tool_input = json.loads(fn["arguments"])
                except (json.JSONDecodeError, TypeError):
                    tool_input = {}
                result = await executor.execute(fn["name"], tool_input)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

    text = (message.get("content") if message else None) or "Извините, что-то пошло не так. Попробуйте ещё раз."
    await append_message(telegram_id, "user", user_message)
    await append_message(telegram_id, "assistant", text)
    return text, {}
