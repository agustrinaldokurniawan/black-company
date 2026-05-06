"""DeepSeek-generated in-character copy; falls back to ``voice`` templates when disabled or on error."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from black_company.company_context import company_context_for_llm
from black_company.state import PairTurn, TeamState

logger = logging.getLogger(__name__)

_llm: Any = None
_llm_failed: bool = False


def deepseek_enabled() -> bool:
    if os.environ.get("BLACK_COMPANY_DISABLE_DEEPSEEK", "").strip().lower() in ("1", "true", "yes"):
        return False
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def deepseek_graph_agents_enabled() -> bool:
    """If False, only Telegram intro/recap use the API — graph nodes use ``voice`` templates (far fewer calls)."""
    if not deepseek_enabled():
        return False
    if os.environ.get("BLACK_COMPANY_DEEPSEEK_TELEGRAM_ONLY", "").strip().lower() in ("1", "true", "yes"):
        return False
    return True


def _get_llm():
    global _llm, _llm_failed
    if _llm is not None:
        return _llm
    if _llm_failed:
        return None
    if not deepseek_enabled():
        return None
    try:
        from black_company.llm.factory import create_deepseek_chat

        _llm = create_deepseek_chat(temperature=0.2, max_tokens=700)
    except (ImportError, ValueError) as e:
        logger.info("DeepSeek unavailable: %s", e)
        _llm_failed = True
        return None
    return _llm


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _spec_substantial_for_team_copy(spec: str | None, *, min_words: int = 6) -> bool:
    """Skip LLM for tiny/vague briefs — model invents UI/tests; templates stay safely generic."""
    s = (spec or "").strip()
    if len(s) < 28:
        return False
    return len(s.split()) >= min_words


GROUNDING_RULES = (
    "GROUNDING (non-negotiable): Use ONLY facts that appear in the text I give you below. "
    "Do not invent screens, buttons, APIs, ticket names, dev names, sprints, metrics, or tests. "
    "If the brief is thin, say the scope is underspecified and suggest what to clarify—do not make up product details."
)


def _complete(system: str, user: str) -> str | None:
    llm = _get_llm()
    if not llm:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        msg = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = (getattr(msg, "content", None) or "").strip()
        return text or None
    except Exception as e:
        logger.warning("DeepSeek completion failed: %s", e)
        return None


_PM_SYSTEM = (
    "You write short, natural internal-comms as a senior product manager. "
    "No markdown headings. No emojis unless the user used them. Keep bullets light if needed. "
    + GROUNDING_RULES
)


def try_telegram_pm_intro(user_message: str) -> str | None:
    body = _clip(user_message, 2000)
    ctx = company_context_for_llm()
    extra = ""
    if len(body.split()) < 6 or len(body) < 32:
        extra = (
            " Their note is very short: acknowledge it, do NOT invent features, "
            "and ask for 2–4 sentences on outcomes and constraints."
        )
    return _complete(
        _PM_SYSTEM
        + " Someone messaged you on Telegram like a teammate."
        + extra
        + " Acknowledge only what they said; mirror the goal if clear. "
        "Ground yourself in company context when it helps. "
        "You’ll need Owner kickoff on this thread next, then Product planning — say that naturally, 2–4 sentences.",
        f"Company context:\n{ctx}\n\nWhat they wrote:\n{body}",
    )


def try_telegram_run_recap(out: dict[str, Any]) -> str | None:
    slim: dict[str, Any] = {
        "status": out.get("status"),
        "qa_result": out.get("qa_result"),
        "owner_kickoff": out.get("owner_kickoff"),
        "owner_acceptance": out.get("owner_acceptance"),
        "pair_round": out.get("pair_round"),
        "planning_iterations": out.get("planning_iterations"),
        "spec_excerpt": _clip(str(out.get("spec") or ""), 900),
        "design_excerpt": _clip(str(out.get("design") or ""), 500),
        "impl_excerpt": _clip(str(out.get("impl") or ""), 500),
        "qa_report_excerpt": _clip(str(out.get("qa_report") or ""), 500),
        "pm_readiness_excerpt": _clip(str(out.get("pm_readiness_summary") or ""), 600),
        "user_agent_notes_excerpt": _clip(str(out.get("user_agent_notes") or ""), 400),
    }
    payload = _clip(json.dumps(slim, ensure_ascii=False, default=str), 3500)
    ctx = company_context_for_llm()
    return _complete(
        _PM_SYSTEM
        + " The engineering workflow just finished (or paused). Summarize for Telegram. "
        "Mention ONLY what appears in the snapshot fields below. "
        "If something is a stub or generic line, say so instead of inventing features. "
        "4–8 short lines. No raw JSON.",
        f"Company context:\n{ctx}\n\nState summary for recap:\n{payload}",
    )


def try_telegram_owner_gate_sidebar(
    user_message: str,
    spec: str | None,
    status: str | None,
    impl_excerpt: str | None = None,
) -> str | None:
    """PM-voice reply during Owner interrupt when user chats instead of voting."""
    if not deepseek_enabled():
        return None
    ctx = company_context_for_llm()
    phase = (
        "Owner acceptance — ship or hold this increment."
        if status == "awaiting_owner_acceptance"
        else "Owner kickoff — approve or reshape the brief before planning and build."
    )
    impl_block = ""
    clipped_impl = _clip(impl_excerpt or "", 900)
    if clipped_impl:
        impl_block = f"\nImplementation notes (excerpt):\n{clipped_impl}\n"
    return _complete(
        "You are the PM on Telegram; the same human often wears the Owner hat. "
        f"They’re formally on: {phase} "
        "They sent a side question instead of a straight vote. "
        "Reply in 2–4 short sentences, like a Slack DM. "
        "Use company context as background only—no brochure dump. "
        "Do NOT explain Telegram mechanics, resume wiring, bots, or footers. "
        "Do NOT paste the whole brief; at most six words quoted if essential. "
        "If they ask where it is deployed or hosted, answer ONLY from implementation notes below if a URL or host is stated; "
        "otherwise say this snapshot doesn’t include a live deploy URL and they should check CI logs or the static host they used. "
        "Say what decision we’re blocked on, nudge yes/no when appropriate. "
        + GROUNDING_RULES,
        f"Company context:\n{ctx}\n\n"
        f"Thread brief (may be thin):\n{_clip(spec or '', 900)}\n"
        f"{impl_block}\n"
        f"They wrote:\n{_clip(user_message, 500)}",
    )


def try_telegram_idle_pm_chat(user_message: str) -> str | None:
    """Conversational PM when no workflow is active — synthesize drafts; avoid question fatigue."""
    if not deepseek_enabled():
        return None
    ctx = company_context_for_llm()
    return _complete(
        "You write short, natural Slack-DM as a senior PM. "
        "No markdown headings. No emojis unless the user used them.\n"
        "No active LangGraph run — informal chat only. Use company context for org facts; "
        "do not invent **verified** company details.\n"
        "ANTI-FATIGUE: If they want something standard (e.g. weather web, current+forecast+history, modern UI, public demo), "
        "do **not** send a long checklist of questions. Prefer **one** short reply with sensible **assumptions** "
        "and a **draft brief** (4–8 lines or tight bullets) they can paste after **New project** or use with **/run**. "
        "At most **one** clarifying question, only if you cannot draft anything. "
        "Direct answers and tradeoffs: keep to ≤8 short lines.\n"
        "Do NOT paste Owner kickoff approval blocks or pretend a gate is waiting.\n"
        "If useful: mention **/help** for channel mechanics.",
        f"Company context:\n{ctx}\n\nThey wrote:\n{_clip(user_message, 1200)}",
    )


def _growth_hint(state: TeamState) -> str:
    g = (state.get("growth_context") or "").strip()
    return _clip(g, 1200) if g else ""


def try_design_handoff(state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    spec_raw = state.get("spec") or ""
    if not _spec_substantial_for_team_copy(spec_raw):
        return None
    spec = _clip(spec_raw, 2500)
    growth = _growth_hint(state)
    user = f"Product brief:\n{spec}\n"
    if growth:
        user += f"\nPast lessons for this PM to respect (if any conflict, brief wins):\n{growth}\n"
    user += "\nWrite the Design handoff to Engineering (bullets: ground truth, UX scope, constraints). Stay practical."
    return _complete(
        "You are Design talking to Eng. Internal Slack style. " + GROUNDING_RULES,
        user,
    )


def try_pair_review(rounds: int, drove: PairTurn, state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    if not _spec_substantial_for_team_copy(state.get("spec")):
        return None
    driver = "Dev 1" if drove == "dev1_drives" else "Dev 2"
    reviewer = "Dev 2" if drove == "dev1_drives" else "Dev 1"
    spec = _clip(state.get("spec") or "", 1200)
    design = _clip(state.get("design") or "", 1200)
    prior_impl = _clip(state.get("impl") or "", 1200)
    return _complete(
        f"You are {reviewer} reviewing {driver}'s work after pair round {rounds}. Internal Eng voice. "
        + GROUNDING_RULES,
        f"Spec:\n{spec}\n\nDesign handoff:\n{design}\n\nLatest implementation notes:\n{prior_impl}\n\n"
        "Write a short pair review: what you checked, what's good, one concrete follow-up.",
    )


def try_pair_impl(rounds: int, drove: PairTurn, state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    if not _spec_substantial_for_team_copy(state.get("spec")):
        return None
    driver = "Dev 1" if drove == "dev1_drives" else "Dev 2"
    reviewer = "Dev 2" if drove == "dev1_drives" else "Dev 1"
    fb = _clip(state.get("review_feedback") or "", 800)
    spec = _clip(state.get("spec") or "", 800)
    return _complete(
        f"You are {driver} driving in pair round {rounds}. {reviewer} will drive next unless you stay in fix mode. "
        "Internal Eng voice. "
        + GROUNDING_RULES,
        f"Spec (excerpt):\n{spec}\n\nLast review feedback:\n{fb}\n\n"
        "Write your checkpoint: what you implemented/tests added, what's next.",
    )


def try_qa_report(rounds: int, *, passing: bool, state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    if not _spec_substantial_for_team_copy(state.get("spec")):
        return None
    verdict = "PASS" if passing else "FAIL"
    impl = _clip(state.get("impl") or "", 1500)
    spec = _clip(state.get("spec") or "", 800)
    return _complete(
        "You are QA signing off on a slice. Be specific but concise; mention risk if failing. " + GROUNDING_RULES,
        f"Verdict must reflect: {verdict} (round {rounds}).\nSpec:\n{spec}\n\nImplementation:\n{impl}\n",
    )


def try_user_planning_notes(iteration: int, satisfied: bool, state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    if not _spec_substantial_for_team_copy(state.get("spec")):
        return None
    phase = "final planning pass — satisfied" if satisfied else "still iterating"
    spec = _clip(state.get("spec") or "", 2000)
    return _complete(
        "You are Product/Stakeholder aligned with PM. Short note to the team. " + GROUNDING_RULES,
        f"Planning iteration {iteration}. Phase: {phase}.\nBrief:\n{spec}\n",
    )


def try_user_ship_notes(ship: str, state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    if not _spec_substantial_for_team_copy(state.get("spec")):
        return None
    summ = _clip(state.get("pm_readiness_summary") or "", 2000)
    tone = (
        "You are comfortable signing off for Owner."
        if ship == "ok"
        else "You have concerns; you want another cycle before Owner."
    )
    return _complete(
        "You are Product at the ship gate. Brief internal voice. " + tone + " " + GROUNDING_RULES,
        f"Agreed spec (excerpt):\n{_clip(state.get('spec') or '', 1200)}\n\nPM readiness summary:\n{summ}\n",
    )


def try_pm_readiness_after_qa(state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    if not _spec_substantial_for_team_copy(state.get("spec")):
        return None
    spec = _clip(state.get("spec") or "", 1500)
    qa = _clip(state.get("qa_report") or "", 1200)
    impl = _clip(state.get("impl") or "", 1200)
    rounds = int(state.get("pair_round") or 0)
    return _complete(
        _PM_SYSTEM + " Write the internal 'release readiness' note before Product ship check. "
        "Tie every sentence to the spec, QA line, or implementation text—nothing else.",
        f"Product spec / brief:\n{spec}\n\nPair rounds complete: {rounds}.\nQA report:\n{qa}\n\n"
        f"Latest implementation:\n{impl}\n",
    )


def try_qa_rework_hint(state: TeamState) -> str | None:
    if not deepseek_graph_agents_enabled():
        return None
    if not _spec_substantial_for_team_copy(state.get("spec")):
        return None
    report = _clip(state.get("qa_report") or "", 1500)
    return _complete(
        "You are PM assigning Eng. One or two sentences: unblock QA, address the report, re-pair. " + GROUNDING_RULES,
        f"QA report:\n{report}\n",
    )
