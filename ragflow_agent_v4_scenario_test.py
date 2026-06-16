from create_ragflow_agent_v4 import ask, create_or_update_agent, extract_answer, login


QUESTIONS = [
    "我是南邮本校学生，想保本校研究生，是看接收推免通知还是校内推免办法？",
    "我家孩子想保研南邮通信学院，现在最应该关注哪几个时间点？",
    "电子信息专业能报哪些学院的推免？",
    "直博和普通推免申请条件有什么不同？",
    "材料学院、化生院、通信学院的材料提交邮箱分别是什么？",
    "如果我没过六级，但是有竞赛奖，还能走校内推免吗？",
    "经济学院和管理学院的推免综合成绩算法一样吗？",
    "我想报计算机学院直博，需要额外提交什么？",
    "哪些学院复试在9月26日？",
    "我收到复试通知后必须马上确认吗？",
    "学校研招办电话和邮箱是多少？",
    "请按时间线告诉我接收推免从填志愿到录取通知书的大概流程",
    "我问的是录取资格，不是复试资格，能不能区分一下？",
    "推免服务系统关闭后还能补报志愿吗？",
    "社会工作学院和社会与人口学院是一个吗？",
    "教育科学与技术学院英语要求是什么？",
    "波特兰学院有推免吗？",
    "如果知识库里没有官方依据，你会怎么回答？",
]


def has_process_leak(answer: str) -> bool:
    head = answer[:120]
    markers = ["我需要检索", "我需要分析", "我需要判断", "用户问", "用户问题", "检索结果", "<think>", "</think>"]
    return any(marker in head for marker in markers)


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    for index, question in enumerate(QUESTIONS, 1):
        answer = extract_answer(ask(session, headers, agent_id, question)).strip()
        print(f"\n===== SCENARIO {index}. {question} =====")
        print(f"leak={has_process_leak(answer)}")
        print(answer[:2000])


if __name__ == "__main__":
    main()
