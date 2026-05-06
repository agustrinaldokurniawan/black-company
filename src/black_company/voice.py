"""In-product copy: internal team tone for stub agents and PM artifacts."""

from __future__ import annotations

from black_company.state import TeamState


def default_project_brief() -> str:
    return (
        "Project brief — PM hub slice:\n"
        "Ship a minimal multi-agent planning → build → QA → ship workflow with "
        "Owner gates, so the team can demo end-to-end delivery with interrupts."
    )


def designer_handoff(state: TeamState) -> str:
    first = (state.get("spec") or "").strip().split("\n")[0][:180]
    headline = first.rstrip(".,;:")
    fallback = "PM's latest brief"
    return (
        "Design — handoff to Engineering\n"
        f"• Ground truth: {headline or fallback}.\n"
        "• UX: primary flow + failure paths sketched; copy aligned with stakeholders.\n"
        "• Ready for pair implementation; escalate to PM if scope creeps."
    )


def pair_session_update(rounds: int, drove: str) -> tuple[str, str]:
    driver = "Dev 1" if drove == "dev1_drives" else "Dev 2"
    reviewer = "Dev 2" if drove == "dev1_drives" else "Dev 1"
    feedback = (
        f"Eng / {reviewer} — Pair review (round {rounds})\n"
        f"• Reviewed {driver}'s latest chunk: conventions OK; one edge case to tighten.\n"
        "• OK to merge to integration branch once local checks pass."
    )
    impl = (
        f"Eng / {driver} — Checkpoint (round {rounds})\n"
        "• Implemented the agreed slice; added coverage on the new boundary.\n"
        f"• Next up: {reviewer} drives unless we stay in fix mode."
    )
    return feedback, impl


def qa_gate_report(rounds: int, *, passing: bool) -> str:
    if passing:
        return (
            f"QA — Sign-off after {rounds} engineering round(s): "
            "checks green; no sev-1/2 open on this slice."
        )
    return (
        f"QA — Blocking at round {rounds}: "
        "pipeline or tests red on touched paths; sending back to pair."
    )


def user_planning_notes(iteration: int, satisfied: bool) -> str:
    if satisfied:
        return (
            f"Product — Planning round {iteration}: "
            "spec matches what we committed to; ready for Owner kickoff."
        )
    return (
        f"Product — Planning round {iteration}: "
        "still tightening acceptance with PM; expect another short loop."
    )


def user_ship_ok_notes() -> str:
    return (
        "Product — Ship gate: aligned with PM's readiness summary; "
        "ok to route to Owner acceptance."
    )


def user_ship_concerns_notes() -> str:
    return (
        "Product — Ship gate: not comfortable signing off yet — "
        "please run another build/review cycle before Owner."
    )


def pm_readiness_after_qa(state: TeamState) -> str:
    rounds = int(state.get("pair_round") or 0)
    qa_line = (state.get("qa_report") or "").strip().replace("\n", " ")
    if len(qa_line) > 260:
        qa_line = qa_line[:257] + "…"
    return (
        "PM — Internal release readiness\n"
        f"• Engineering: pair closed {rounds} round(s); integration branch current.\n"
        f"• QA: {qa_line}\n"
        "• Next: Product ship check, then Owner only if Product is green."
    )


def qa_rework_hint() -> str:
    return "Engineering — QA blocked the merge; address the report and re-pair."
