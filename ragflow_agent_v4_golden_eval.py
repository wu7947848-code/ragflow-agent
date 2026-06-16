from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from create_ragflow_agent_v4 import BASE, create_or_update_agent, extract_answer, login


ROOT = Path(__file__).resolve().parent
DEFAULT_SPEC = ROOT / "ragflow_agent_v4_golden_eval.json"

GLOBAL_FORBIDDEN = [
    "系统提示",
    "系统指令",
    "用户问",
    "用户问题",
    "检索策略",
    "结构化事实层ID",
    "官方原文层ID",
    "[ID:",
    "<think>",
    "</think>",
    "志原",
    "代录取",
    "RAGFlow-ready v3",
    "根据检索结果",
    "根据检索到的信息",
    "检索显示",
]

REQUIRED_SECTIONS = ["答案：", "依据：", "适用范围：", "提醒："]


def load_spec(path: Path = DEFAULT_SPEC) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_must_any(value: Any) -> list[list[str]]:
    if not value:
        return []
    if all(isinstance(item, str) for item in value):
        return [list(value)]
    groups: list[list[str]] = []
    for item in value:
        if isinstance(item, str):
            groups.append([item])
        else:
            groups.append(list(item))
    return groups


def has_process_leak(answer: str) -> bool:
    head = answer[:180]
    return any(marker in head for marker in GLOBAL_FORBIDDEN)


def check_answer(answer: str, case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if has_process_leak(answer):
        failures.append("process text leaked")
    if not answer.startswith("答案："):
        failures.append("answer does not start with 答案：")
    for label in REQUIRED_SECTIONS:
        if label not in answer:
            failures.append(f"required section missing: {label}")
    for marker in case.get("must", []):
        if marker not in answer:
            failures.append(f"required marker missing: {marker}")
    for group in normalize_must_any(case.get("must_any")):
        if not any(marker in answer for marker in group):
            failures.append(f"one of required markers missing: {group}")
    for marker in [*GLOBAL_FORBIDDEN, *case.get("forbid", [])]:
        if marker and marker in answer:
            label = "process marker" if marker in GLOBAL_FORBIDDEN else "forbidden marker"
            failures.append(f"{label} found: {marker}")
    if re.search(r"\bID:\d+|\[ID:\d+\]", answer):
        failures.append("internal retrieval ID leaked")
    return sorted(set(failures))


def ask_with_session(session, headers: dict[str, str], agent_id: str, query: str, session_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"agent_id": agent_id, "query": query, "stream": False, "return_trace": True}
    if session_id:
        body["session_id"] = session_id
    response = session.post(f"{BASE}/api/v1/agents/chat/completions", headers=headers, json=body, timeout=120)
    response.raise_for_status()
    return response.json()


def get_session_id(result: dict[str, Any]) -> str | None:
    data = result.get("data", result)
    if isinstance(data, dict):
        if data.get("session_id"):
            return str(data["session_id"])
        nested = data.get("data")
        if isinstance(nested, dict):
            session_id = nested.get("session_id") or nested.get("id")
            return str(session_id) if session_id else None
    return None


def case_matches_filters(case: dict[str, Any], categories: set[str], tags: set[str]) -> bool:
    if categories and case.get("category") not in categories:
        return False
    if tags and not tags.intersection(set(case.get("tags", []))):
        return False
    return True


def run_single_cases(session, headers: dict[str, str], agent_id: str, cases: list[dict[str, Any]]) -> bool:
    failed = False
    for case in cases:
        result = ask_with_session(session, headers, agent_id, case["query"])
        answer = extract_answer(result).strip()
        failures = check_answer(answer, case)
        print(f"\n===== SINGLE {case['id']} [{case['category']}] =====")
        print(f"query={case['query']}")
        print(f"failures={failures}")
        print(answer[:1800])
        failed |= bool(failures)
    return failed


def run_conversations(session, headers: dict[str, str], agent_id: str, cases: list[dict[str, Any]]) -> bool:
    failed = False
    for case in cases:
        print(f"\n========== CONVERSATION {case['id']} [{case['category']}] ==========")
        session_id: str | None = None
        for index, turn in enumerate(case["turns"], 1):
            result = ask_with_session(session, headers, agent_id, turn["query"], session_id)
            session_id = get_session_id(result) or session_id
            answer = extract_answer(result).strip()
            failures = check_answer(answer, turn)
            if index > 1 and not session_id:
                failures.append("session_id was not preserved")
            print(f"\n--- Turn {index}: {turn['query']}")
            print(f"session_id={session_id} failures={failures}")
            print(answer[:1800])
            failed |= bool(failures)
    return failed


def parse_csv_filter(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGFlow v4 golden eval cases.")
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--category", help="Comma-separated category filter.")
    parser.add_argument("--tag", help="Comma-separated tag filter.")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    spec = load_spec(args.spec)
    categories = parse_csv_filter(args.category)
    tags = parse_csv_filter(args.tag)
    single_cases = [case for case in spec["single_turn_cases"] if case_matches_filters(case, categories, tags)]
    conversation_cases = [case for case in spec["conversation_cases"] if case_matches_filters(case, categories, tags)]

    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    print(f"spec={args.spec}")
    print(f"single_cases={len(single_cases)} conversation_cases={len(conversation_cases)} repeat={args.repeat}")

    failed = False
    for round_index in range(1, args.repeat + 1):
        print(f"\n########## GOLDEN EVAL ROUND {round_index}/{args.repeat} ##########")
        failed |= run_single_cases(session, headers, agent_id, single_cases)
        failed |= run_conversations(session, headers, agent_id, conversation_cases)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
