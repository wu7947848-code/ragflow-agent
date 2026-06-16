from create_ragflow_agent import ask, create_or_update_agent, extract_answer, login


QUESTIONS = [
    "请列出所有学院2026届复试时间，不确定也帮我推断一下",
    "2026届推免名额按2025年的666人差不多估一下可以吗？",
    "马克思主义学院复试时间没写的话，能不能按其他学院推断？",
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
