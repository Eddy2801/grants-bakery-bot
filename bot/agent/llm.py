"""
LLM agent — Claude Haiku with tool_use.
Single-turn: receives conversation history + new message, returns reply text.
"""
import logging
from typing import Any

import anthropic

from bot.config import config
from bot.agent.prompts import get_system_prompt
from bot.agent.tools import TOOLS, ToolExecutor
from bot.redis_client import get_conversation, append_message

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


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
        pending_actions: {
            "pending_order": {...} | None,
            "pending_subscription": {...} | None,
        }
    """
    client = get_client()
    system = get_system_prompt(intent, lang)

    # Build message history (last 8 messages for context)
    history = await get_conversation(telegram_id)

    # Add current user message to history for the API call
    messages = history + [{"role": "user", "content": user_message}]

    executor = ToolExecutor(telegram_id=telegram_id, user_id=user_id, lang=lang)

    # Agentic loop — max 5 tool-call rounds
    for _round in range(5):
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        logger.debug("LLM response stop_reason=%s", response.stop_reason)

        if response.stop_reason == "end_turn":
            # Final text response
            text = _extract_text(response)
            # Save conversation
            await append_message(telegram_id, "user", user_message)
            await append_message(telegram_id, "assistant", text)
            return text, {
                "pending_order": executor._pending_order or None,
                "pending_subscription": executor._pending_subscription or None,
            }

        if response.stop_reason == "tool_use":
            # Execute all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await executor.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Append assistant + tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Fallback
    text = _extract_text(response) or "Извините, что-то пошло не так. Попробуйте ещё раз."
    await append_message(telegram_id, "user", user_message)
    await append_message(telegram_id, "assistant", text)
    return text, {}


def _extract_text(response: Any) -> str:
    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            return block.text
    return ""
