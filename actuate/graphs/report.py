"""Serialize a graph run the same way the console inspector does."""

from __future__ import annotations

from typing import Any


def node_status(trace: dict[str, Any] | None, *, run_status: str) -> str:
    if not trace:
        return "not_run"
    if trace.get("frozen"):
        return "frozen"
    if trace.get("outputs"):
        scores = trace.get("scores") or []
        if scores and float(scores[-1]) < 0.8 and str(trace.get("agent", "")).startswith("judge"):
            return "failed"
        return "completed"
    if trace.get("inputs"):
        return "running" if run_status == "running" else "failed"
    return "not_run"


def pass_report(result: dict[str, Any]) -> dict[str, Any]:
    traces = {t.get("node_id"): t for t in (result.get("traces") or []) if t.get("node_id")}
    nodes_meta = (result.get("graph") or {}).get("nodes") or []
    nodes = []
    for meta in nodes_meta:
        nid = meta.get("id")
        t = traces.get(nid) or {}
        nodes.append(
            {
                "node_id": nid,
                "agent": meta.get("agent") or t.get("agent"),
                "title": meta.get("label") or t.get("title") or meta.get("agent"),
                "status": node_status(t or None, run_status=str(result.get("status") or "")),
                "inputs": t.get("inputs") or [],
                "outputs": t.get("outputs") or [],
                "scores": t.get("scores") or [],
                "feedback": t.get("feedback") or [],
                "tokens": t.get("tokens") or 0,
                "latency_seconds": t.get("latency_seconds") or 0,
                "passes": t.get("passes") or 0,
            }
        )
    return {
        "status": result.get("status"),
        "reward": result.get("reward"),
        "reward_mean": result.get("reward_mean"),
        "passes": result.get("passes"),
        "tokens": result.get("tokens"),
        "latency_seconds": result.get("latency_seconds"),
        "stop_reason": result.get("stop_reason"),
        "judge_scores": result.get("judge_scores") or {},
        "nodes": nodes,
    }


def run_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "pass": pass_report(result),
        "final_output": result.get("output") or "",
    }
