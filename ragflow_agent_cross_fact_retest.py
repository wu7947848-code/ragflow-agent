from create_ragflow_agent import ask, create_or_update_agent, extract_answer, login


QUESTIONS = [
    "电子信息专业能报哪些学院的推免？",
    "材料学院、化生院、通信学院的材料提交邮箱分别是什么？",
    "教育科学与技术学院英语要求是什么？",
    "我想报计算机学院直博，需要额外提交什么？",
]


def main():
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for question in QUESTIONS:
        answer = extract_answer(ask(session, headers, agent_id, question)).strip()
        print(f"\n=== {question} ===")
        print(answer[:2000])


if __name__ == "__main__":
    main()
