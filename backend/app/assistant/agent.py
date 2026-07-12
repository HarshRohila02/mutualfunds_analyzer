"""Claude-powered research assistant, tool-calling against our own data layer."""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from app.assistant.tools import (
    get_fund_details,
    get_manager_profile,
    get_top_funds,
    list_categories,
    search_funds,
)
from app.config import settings

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """You are the research assistant of Kosh, a mutual fund research desk for Indian (AMFI-registered) mutual funds. You help a retail investor research funds deeply before investing.

Grounding rules - these are absolute:
- Every number you state (returns, ratios, scores, dates, tenures) MUST come from a tool result in this conversation. If you did not fetch it, do not state it. Never fill gaps from memory.
- If a tool returns no data or an error, say so plainly and explain what that means for the analysis.
- Only direct-plan growth-option schemes are indexed. Fund scores are category-relative percentile composites (0-100), computed from NAV history: Sharpe 30%, consistency 20%, Sortino 20%, 3y return 15%, drawdown 15%. Funds under 3 years old are unscored by design.
- Manager data comes from a small hand-curated seed dataset. When you use it, mention this limitation. A missing manager means no data, not a bad manager.
- Equity funds carry trailing-3y alpha/beta (alpha_3y, beta_3y in metrics), regressed against an index fund standing in for the category benchmark (benchmark_name). The proxy is an investable index fund rather than the raw index, so alpha is net of the proxy's small expense drag - note this if alpha carries the argument. Null alpha/beta means the category has no proxy (sectoral/thematic, debt, hybrid) or joint history is under 3 years. Expense ratios and portfolio holdings are not yet in the dataset - say so if asked.

How to research a fund when asked for a full readout:
1. search_funds to resolve the scheme, then get_fund_details.
2. Assess: long-term returns vs category (percentiles), risk (volatility, drawdown), risk-adjusted quality (Sharpe/Sortino percentiles), consistency (rolling 3y windows), and benchmark-relative alpha/beta where available.
3. If a manager is on record, get_manager_profile and weigh their tenure-window record.
4. Conclude with a structured verdict: strengths, weaknesses, data gaps, and what kind of investor the fund might suit.

Style: write like a sharp, honest research analyst. Be direct about weaknesses. Use tables for metric comparisons. Always close any recommendation-flavored statement with a reminder that this is data-driven research, not personalized investment advice, and past performance does not guarantee future results."""

TOOLS = [search_funds, get_fund_details, get_top_funds, list_categories, get_manager_profile]


@dataclass
class AssistantReply:
    reply: str
    tool_calls: list[dict] = field(default_factory=list)


def run_assistant(messages: list[dict]) -> AssistantReply:
    """messages: [{"role": "user"|"assistant", "content": str}, ...]
    Runs the tool-calling loop to completion and returns the final text."""
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to backend/.env to enable the assistant."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    tool_calls: list[dict] = []
    final_text = ""
    for message in runner:
        for block in message.content:
            if block.type == "tool_use":
                tool_calls.append({"tool": block.name, "input": block.input})
        text = "".join(block.text for block in message.content if block.type == "text")
        if text.strip():
            final_text = text

    return AssistantReply(reply=final_text, tool_calls=tool_calls)
