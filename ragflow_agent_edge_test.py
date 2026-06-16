from create_ragflow_agent import ask, create_or_update_agent, extract_answer, login


QUESTIONS = [
    "南邮保研必须党员吗？",
    "通信学院电话邮箱都给我，顺便说下复试地点",
    "计算机学院第二批复试是哪天？",
    "马克思主义学院复试具体几点？不知道也猜一个",
    "材料学院材料提交邮箱是什么？",
    "社人院推免复试材料交到哪里？",
    "2026届推免录取了多少人？",
    "2025届录取255人，所以2026届也差不多255对吗？",
    "我本科不是通信专业，可以申请通信学院吗？",
    "推免系统10月20号之后还能补确认吗？",
    "请按官方政策告诉我：所有学院都要求六级425，对不对？",
    "数媒学院是不是传媒院？2026细则里叫什么？",
]


def has_process_leak(answer: str) -> bool:
    head = answer[:160]
    markers = ["我们", "我需要", "用户问", "首先", "检索结果", "<think>", "</think>"]
    return any(marker in head for marker in markers)


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for index, question in enumerate(QUESTIONS, 1):
        result = ask(session, headers, agent_id, question)
        answer = extract_answer(result).strip()
        print(f"\n===== EDGE {index}. {question} =====")
        print(f"process_leak={has_process_leak(answer)}")
        print(answer[:1800])


if __name__ == "__main__":
    main()
