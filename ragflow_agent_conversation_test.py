from create_ragflow_agent import login, create_or_update_agent, extract_answer


CONVERSATIONS = [
    [
        "通信学院推免材料发到哪个邮箱？",
        "那它的电话是多少？",
        "复试地点有写吗？",
    ],
    [
        "材料学院材料提交邮箱是什么？",
        "张老师电话也给我",
        "这个邮箱是复试细则原文写的吗？",
    ],
    [
        "计算机学院第二批复试时间？",
        "第一批呢？",
        "材料要怎么交？",
    ],
    [
        "2026届推免名额是多少？",
        "那2025届是多少？",
        "所以能不能推断2026也差不多？",
    ],
    [
        "我问的是校内保研资格，不是接收外校推免",
        "英语必须六级425吗？",
        "竞赛通道呢？",
    ],
]


def converse(session, headers, agent_id, query, session_id=None):
    payload = {
        "agent_id": agent_id,
        "query": query,
        "stream": False,
        "return_trace": True,
    }
    if session_id:
        payload["session_id"] = session_id
    response = session.post(
        "http://localhost/api/v1/agents/chat/completions",
        headers=headers,
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    result = response.json()
    data = result.get("data", {})
    new_session_id = data.get("session_id") if isinstance(data, dict) else None
    return extract_answer(result).strip(), new_session_id


def main():
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for i, turns in enumerate(CONVERSATIONS, 1):
        print(f"\n========== CONVERSATION {i} ==========")
        session_id = None
        for j, question in enumerate(turns, 1):
            answer, session_id = converse(session, headers, agent_id, question, session_id)
            leak = any(marker in answer[:120] for marker in ["我需要", "用户问", "<think>", "</think>"])
            print(f"\n--- Turn {j}: {question}")
            print(f"session_id={session_id} leak={leak}")
            print(answer[:1400])


if __name__ == "__main__":
    main()
