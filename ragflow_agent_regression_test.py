from create_ragflow_agent import ask, create_or_update_agent, extract_answer, login


QUESTIONS = [
    "南邮今年保研名额多少？",
    "2026年推免申请要满足什么条件？",
    "我想问校内获得推免资格的条件，不是接收外校推免，知识库里有吗？",
    "通信学院推免材料发到哪个邮箱？",
    "计算机学院推免材料怎么提交？",
    "自动化学院和人工智能学院是一起复试吗？",
    "经济学院保研综合排名怎么算？",
    "如果我确认了待录取通知，后面还能改吗？",
    "物联网学院2026届复试时间和邮箱是什么？",
    "2025年的推免名额是不是可以直接作为2026年的参考？",
    "请列出所有学院2026届复试时间，不确定也帮我推断一下",
    "南京邮电大学保研是不是要求英语六级必须425分？",
]


def has_process_leak(answer: str) -> bool:
    head = answer[:120]
    markers = ["我们", "我需要", "用户问", "首先", "检索结果", "<think>", "</think>"]
    return any(marker in head for marker in markers)


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for index, question in enumerate(QUESTIONS, 1):
        result = ask(session, headers, agent_id, question)
        answer = extract_answer(result).strip()
        print(f"\n===== {index}. {question} =====")
        print(f"process_leak={has_process_leak(answer)}")
        print(answer[:1800])


if __name__ == "__main__":
    main()
