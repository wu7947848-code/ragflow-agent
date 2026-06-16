from create_ragflow_agent import create_or_update_agent, login
from ragflow_agent_conversation_test import converse


CASES = [
    [
        "计算机学院第二批复试时间？",
        "第一批呢？",
        "材料要怎么交？",
    ],
    [
        "我问的是校内保研资格，不是接收外校推免",
        "英语必须六级425吗？",
        "竞赛通道呢？",
    ],
]


def main():
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for i, turns in enumerate(CASES, 1):
        print(f"\n========== FOCUSED {i} ==========")
        session_id = None
        for question in turns:
            answer, session_id = converse(session, headers, agent_id, question, session_id)
            print(f"\nQ: {question}")
            print(answer[:1600])


if __name__ == "__main__":
    main()
