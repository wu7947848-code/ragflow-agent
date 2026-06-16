from __future__ import annotations

from typing import Any

from create_ragflow_agent_v4 import create_or_update_agent, extract_answer, login
from ragflow_agent_v4_golden_eval import ask_with_session, get_session_id


STATE_COMPONENT = "LLM:ExtractState"
RESOLVE_COMPONENT = "LLM:ResolveQuery"


def trace_output(result: dict[str, Any], component_id: str) -> str:
    data = result.get("data", result)
    if isinstance(data, dict):
        nested = data.get("data")
        if isinstance(nested, dict):
            trace_items = nested.get("trace", [])
        else:
            trace_items = data.get("trace", [])
    else:
        trace_items = []

    for item in trace_items:
        if item.get("component_id") != component_id:
            continue
        for step in item.get("trace", []):
            outputs = step.get("outputs") or {}
            content = outputs.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def require_markers(text: str, markers: list[str], label: str) -> list[str]:
    return [f"{label} missing marker: {marker}" for marker in markers if marker not in text]


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    failed = False

    conversations = [
        {
            "name": "推荐端边界纠正后继承政策端",
            "turns": [
                {
                    "query": "我问的是校内保研资格，不是接收外校推免",
                    "state": ["政策端=推荐端", "届别=2026届"],
                    "resolved": ["校内", "推荐端"],
                },
                {
                    "query": "英语必须六级425吗？",
                    "state": ["政策端=推荐端", "对象=英语要求"],
                    "resolved": ["推荐端", "英语", "CET-6"],
                    "answer_must": ["CET-6", "CET-4"],
                    "answer_forbid": ["请先确认", "计算机学院"],
                },
            ],
        },
        {
            "name": "学院与批次追问",
            "turns": [
                {
                    "query": "计算机学院第二批复试时间？",
                    "state": ["学院=计算机学院、软件学院、网络空间安全学院", "政策端=接收端", "批次=第二批"],
                    "resolved": ["计算机学院", "第二批"],
                    "answer_must": ["10月16日", "15:00"],
                },
                {
                    "query": "第一批呢？",
                    "state": ["学院=计算机学院、软件学院、网络空间安全学院", "政策端=接收端", "批次=第一批"],
                    "resolved": ["计算机学院", "第一批"],
                    "answer_must": ["9月24日", "8:30"],
                    "answer_forbid": ["请先说明"],
                },
            ],
        },
    ]

    for conversation in conversations:
        print(f"\n========== {conversation['name']} ==========")
        session_id: str | None = None
        for index, turn in enumerate(conversation["turns"], 1):
            result = ask_with_session(session, headers, agent_id, turn["query"], session_id)
            session_id = get_session_id(result) or session_id
            state = trace_output(result, STATE_COMPONENT)
            resolved = trace_output(result, RESOLVE_COMPONENT)
            answer = extract_answer(result).strip()

            failures: list[str] = []
            if not state:
                failures.append(f"{STATE_COMPONENT} output missing")
            if not resolved:
                failures.append(f"{RESOLVE_COMPONENT} output missing")
            failures.extend(require_markers(state, turn.get("state", []), "state"))
            failures.extend(require_markers(resolved, turn.get("resolved", []), "resolved query"))
            failures.extend(require_markers(answer, turn.get("answer_must", []), "answer"))
            for marker in turn.get("answer_forbid", []):
                if marker in answer:
                    failures.append(f"answer forbidden marker found: {marker}")
            if index > 1 and not session_id:
                failures.append("session_id was not preserved")

            print(f"\n--- Turn {index}: {turn['query']}")
            print(f"session_id={session_id}")
            print(f"state={state}")
            print(f"resolved={resolved}")
            print(f"failures={failures}")
            print(answer[:1200])
            failed |= bool(failures)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
