from create_ragflow_agent import ask, create_or_update_agent, extract_answer, login


QUESTIONS = [
    "我家孩子想保研南邮通信学院，现在最应该关注哪几个时间点？",
    "哪些学院复试在9月26日？",
    "教育科学与技术学院英语要求是什么？",
    "经济学院和管理学院的推免综合成绩算法一样吗？",
    "波特兰学院有推免吗？",
]


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for question in QUESTIONS:
        answer = extract_answer(ask(session, headers, agent_id, question)).strip()
        print(f"\n=== {question} ===")
        print(answer[:2000])


if __name__ == "__main__":
    main()
