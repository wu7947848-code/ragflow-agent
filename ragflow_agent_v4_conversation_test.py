from create_ragflow_agent_v4 import BASE, ask, create_or_update_agent, extract_answer, login


CONVERSATIONS = [
    ["通信学院推免材料发到哪个邮箱？", "那它的电话是多少？", "复试地点有写吗？"],
    ["材料学院材料提交邮箱是什么？", "张老师电话也给我", "这个邮箱是复试细则原文写的吗？"],
    ["计算机学院第二批复试时间？", "第一批呢？", "材料要怎么交？"],
    ["2026届推免名额是多少？", "那2025届是多少？", "所以能不能推断2026也差不多？"],
    ["我问的是校内保研资格，不是接收外校推免", "英语必须六级425吗？", "竞赛通道呢？"],
]


def has_process_leak(answer: str) -> bool:
    head = answer[:120]
    markers = ["我需要检索", "我需要分析", "我需要判断", "用户问", "用户问题", "检索结果", "<think>", "</think>"]
    return any(marker in head for marker in markers)


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


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for index, turns in enumerate(CONVERSATIONS, 1):
        print(f"\n========== CONVERSATION {index} ==========")
        session_id = None
        failed = False
        for turn_index, question in enumerate(turns, 1):
            result = ask_with_session(session, headers, agent_id, question, session_id)
            session_id = get_session_id(result) or session_id
            answer = extract_answer(result).strip()
            leak = has_process_leak(answer)
            print(f"\n--- Turn {turn_index}: {question}")
            print(f"session_id={session_id} leak={leak}")
            print(answer[:1600])
            if leak:
                failed = True
            if turn_index > 1 and not session_id:
                print("failure=session_id was not preserved")
                failed = True
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
