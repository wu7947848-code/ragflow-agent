from __future__ import annotations

from create_ragflow_agent_v4 import BASE, create_or_update_agent, extract_answer, login


CONVERSATIONS = [
    {
        "name": "通信学院代词追问",
        "turns": [
            {"query": "通信学院推免材料发到哪个邮箱？", "must": ["scie-yz@njupt.edu.cn"]},
            {"query": "那它的电话是多少？", "must": ["025-83492075", "通信"], "forbid": ["请先说明"]},
            {"query": "复试地点有写吗？", "must_any": ["腾讯会议", "网络远程"], "forbid": ["请先说明"]},
        ],
    },
    {
        "name": "材料学院邮箱来源追问",
        "turns": [
            {"query": "材料学院材料提交邮箱是什么？", "must": ["iammzhang@njupt.edu.cn"]},
            {"query": "张老师电话也给我", "must": ["025-85866533", "张老师"], "forbid": ["请先说明"]},
            {
                "query": "这个邮箱是复试细则原文写的吗？",
                "must": ["研究生招生信息网", "培养单位联系方式"],
                "must_any": ["不是复试细则正文直接列出", "不是复试细则原件正文直接写明", "邮箱来自研招网", "来源为研招网"],
                "forbid": ["请先说明", "是复试细则原文写的"],
            },
        ],
    },
    {
        "name": "计算机学院批次追问",
        "turns": [
            {"query": "计算机学院第二批复试时间？", "must": ["10月16日", "15:00"]},
            {"query": "第一批呢？", "must": ["9月24日", "8:30"], "forbid": ["请先说明"]},
            {"query": "材料要怎么交？", "must": ["jsjzs@njupt.edu.cn", "姓名+学校"], "forbid": ["请先说明"]},
        ],
    },
    {
        "name": "推荐端边界追问",
        "turns": [
            {"query": "我问的是校内保研资格，不是接收外校推免", "must": ["推荐端"], "forbid": ["计算机学院"]},
            {"query": "英语必须六级425吗？", "must": ["CET-6", "CET-4", "竞赛"], "forbid": ["请先确认", "计算机学院"]},
            {"query": "竞赛通道呢？", "must": ["学校认可的重要学科竞赛", "国家级三等奖"], "forbid": ["请先确认"]},
        ],
    },
]


def ask_with_session(session, headers, agent_id: str, query: str, session_id: str | None) -> dict:
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


def check_answer(answer: str, case: dict) -> list[str]:
    failures: list[str] = []
    for marker in case.get("must", []):
        if marker not in answer:
            failures.append(f"required marker missing: {marker}")
    if case.get("must_any") and not any(marker in answer for marker in case["must_any"]):
        failures.append(f"one of required markers missing: {case['must_any']}")
    for marker in case.get("forbid", []):
        if marker in answer:
            failures.append(f"forbidden marker found: {marker}")
    if not answer.startswith("答案："):
        failures.append("answer does not start with 答案：")
    return failures


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
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
                failures.append("session_id was not preserved for follow-up")
            print(f"\n--- Turn {index}: {turn['query']}")
            print(f"session_id={session_id} failures={failures}")
            print(answer[:1600])
            if failures:
                failed = True

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
