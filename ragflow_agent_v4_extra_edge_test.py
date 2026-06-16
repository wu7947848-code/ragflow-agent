from __future__ import annotations

from create_ragflow_agent_v4 import BASE, create_or_update_agent, extract_answer, login


NEW_SESSION_CASES = [
    {
        "query": "那它的电话是多少？",
        "must": ["请先说明", "学院"],
        "forbid": ["025-83492075", "025-85866533", "025-83492451"],
    },
    {
        "query": "这个邮箱是复试细则原文写的吗？",
        "must": ["请先说明", "学院"],
        "forbid": ["iammzhang@njupt.edu.cn", "scie-yz@njupt.edu.cn", "是复试细则原文"],
    },
    {
        "query": "张老师电话也给我",
        "must": ["请先说明", "学院"],
        "forbid": ["025-85866533"],
    },
    {
        "query": "第一批呢？",
        "must": ["请先说明", "学院"],
        "forbid": ["9月24日8:30", "9月24日13:30", "计算机学院", "管理学院"],
    },
    {
        "query": "第二批复试时间？",
        "must": ["请先说明", "学院"],
        "forbid": ["10月16日15:00", "计算机学院"],
    },
    {
        "query": "材料要怎么交？",
        "must": ["请先说明", "学院"],
        "forbid": ["scie-yz@njupt.edu.cn", "jsjzs@njupt.edu.cn", "iammzhang@njupt.edu.cn"],
    },
]


DIRECT_ANSWER_CASES = [
    {
        "query": "哪些学院复试在9月26日？",
        "must": ["物联网学院", "数字媒体", "9月26日"],
        "forbid": ["请先说明"],
    },
    {
        "query": "学校研招办电话和邮箱是多少？",
        "must": ["025-83492350", "yzb@njupt.edu.cn"],
        "forbid": ["请先说明", "请先确认"],
    },
    {
        "query": "物联网学院材料提交邮箱是什么？",
        "must": ["未明示", "iot@njupt.edu.cn"],
        "forbid": ["fangw@njupt.edu.cn"],
    },
    {
        "query": "校内推荐端材料能发到通信学院那个邮箱吗？",
        "must": ["不能", "推荐端", "接收端"],
        "forbid": ["可以发", "可以直接发"],
    },
]


CONVERSATIONS = [
    {
        "name": "通信学院上下文后纠正为推荐端",
        "turns": [
            {"query": "通信学院材料提交邮箱是什么？", "must": ["scie-yz@njupt.edu.cn"]},
            {"query": "我问的是校内保研资格，不是接收端材料", "must": ["推荐端"], "forbid": ["scie-yz@njupt.edu.cn"]},
            {"query": "英语是不是必须六级425？", "must": ["CET-6", "CET-4", "推荐端"], "forbid": ["scie-yz@njupt.edu.cn"]},
        ],
    },
    {
        "name": "材料学院邮箱来源连续追问",
        "turns": [
            {"query": "材料学院材料提交邮箱是什么？", "must": ["iammzhang@njupt.edu.cn", "南京邮电大学研究生招生信息网"]},
            {
                "query": "这个邮箱是复试细则原文直接写的吗？",
                "must": ["不是", "南京邮电大学研究生招生信息网", "来源为研招网培养单位联系方式"],
                "forbid": ["是的", "是复试细则正文直接列出", "细则正文直接列出了"],
            },
        ],
    },
    {
        "name": "跨会话批次上下文只在本会话生效",
        "turns": [
            {"query": "计算机学院第二批复试时间？", "must": ["10月16日", "15:00"]},
            {"query": "第一批呢？", "must": ["9月24日", "8:30"], "forbid": ["请先说明"]},
        ],
    },
]


def ask_with_session(session, headers, agent_id: str, query: str, session_id: str | None = None) -> dict:
    body = {"agent_id": agent_id, "query": query, "stream": False, "return_trace": True}
    if session_id:
        body["session_id"] = session_id
    response = session.post(f"{BASE}/api/v1/agents/chat/completions", headers=headers, json=body, timeout=120)
    response.raise_for_status()
    return response.json()


def get_session_id(result: dict) -> str | None:
    data = result.get("data", result)
    if isinstance(data, dict):
        if data.get("session_id"):
            return data["session_id"]
        nested = data.get("data")
        if isinstance(nested, dict):
            return nested.get("session_id") or nested.get("id")
    return None


def has_process_leak(answer: str) -> bool:
    head = answer[:160]
    markers = ["我需要检索", "我需要分析", "我需要判断", "用户问", "用户问题", "检索结果", "<think>", "</think>"]
    return any(marker in head for marker in markers)


def check_answer(answer: str, case: dict) -> list[str]:
    failures: list[str] = []
    if has_process_leak(answer):
        failures.append("process text leaked")
    if not answer.startswith("答案："):
        failures.append("answer does not start with 答案：")
    for marker in case.get("must", []):
        if marker not in answer:
            failures.append(f"required marker missing: {marker}")
    if case.get("must_any") and not any(marker in answer for marker in case["must_any"]):
        failures.append(f"one of required markers missing: {case['must_any']}")
    for marker in case.get("forbid", []):
        if marker in answer:
            failures.append(f"forbidden marker found: {marker}")
    return failures


def run_single_cases(session, headers, agent_id: str, label: str, cases: list[dict]) -> bool:
    failed = False
    for index, case in enumerate(cases, 1):
        result = ask_with_session(session, headers, agent_id, case["query"])
        answer = extract_answer(result).strip()
        failures = check_answer(answer, case)
        print(f"\n===== {label} {index}. {case['query']} =====")
        print(f"failures={failures}")
        print(answer[:1600])
        if failures:
            failed = True
    return failed


def run_conversations(session, headers, agent_id: str) -> bool:
    failed = False
    for conversation in CONVERSATIONS:
        print(f"\n========== {conversation['name']} ==========")
        session_id: str | None = None
        for index, turn in enumerate(conversation["turns"], 1):
            result = ask_with_session(session, headers, agent_id, turn["query"], session_id)
            session_id = get_session_id(result) or session_id
            answer = extract_answer(result).strip()
            failures = check_answer(answer, turn)
            if index > 1 and not session_id:
                failures.append("session_id was not preserved")
            print(f"\n--- Turn {index}: {turn['query']}")
            print(f"session_id={session_id} failures={failures}")
            print(answer[:1600])
            if failures:
                failed = True
    return failed


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    failed = False
    failed |= run_single_cases(session, headers, agent_id, "NEW_SESSION", NEW_SESSION_CASES)
    failed |= run_single_cases(session, headers, agent_id, "DIRECT", DIRECT_ANSWER_CASES)
    failed |= run_conversations(session, headers, agent_id)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
