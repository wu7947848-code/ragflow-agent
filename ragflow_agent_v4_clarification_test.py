from __future__ import annotations

from create_ragflow_agent_v4 import ask, create_or_update_agent, extract_answer, login


CLARIFICATION_CASES = [
    {
        "query": "材料怎么交？",
        "must": ["请先说明", "学院"],
        "forbid": ["scie-yz@njupt.edu.cn", "jsjzs@njupt.edu.cn", "iammzhang@njupt.edu.cn", "fangw@njupt.edu.cn"],
    },
    {
        "query": "这个学院的邮箱是多少？",
        "must": ["请先说明", "学院"],
        "forbid": ["scie-yz@njupt.edu.cn", "jsjzs@njupt.edu.cn", "iammzhang@njupt.edu.cn", "iot@njupt.edu.cn"],
    },
    {
        "query": "第一批呢？",
        "must": ["请先说明", "学院"],
        "forbid": ["管理学院", "9月24日13:30", "jsjzs@njupt.edu.cn"],
    },
    {
        "query": "第二批复试时间？",
        "must": ["请先说明", "学院"],
        "forbid": ["计算机学院", "10月16日15:00", "管理学院"],
    },
    {
        "query": "保研条件是什么？",
        "must": ["请先确认", "推荐端", "接收端"],
        "forbid": ["CET-6", "六级425", "申请人须获得所在学校推免资格"],
    },
]


ANSWERABLE_CASES = [
    {
        "query": "通信学院接收推免材料发到哪个邮箱？",
        "must": ["scie-yz@njupt.edu.cn", "接收端"],
        "forbid": ["请先说明", "请先确认"],
    },
    {
        "query": "计算机学院直博需要额外提交什么？",
        "must": ["两名", "教授"],
        "forbid": ["请先说明", "请先确认"],
    },
    {
        "query": "学校研招办电话和邮箱是多少？",
        "must": ["025-83492350", "yzb@njupt.edu.cn"],
        "forbid": ["请先说明", "请先确认"],
    },
]


def check_case(answer: str, must: list[str], forbid: list[str]) -> list[str]:
    failures: list[str] = []
    for marker in must:
        if marker not in answer:
            failures.append(f"required marker missing: {marker}")
    for marker in forbid:
        if marker in answer:
            failures.append(f"forbidden marker found: {marker}")
    return failures


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")

    failed = False
    for label, cases in [("CLARIFY", CLARIFICATION_CASES), ("ANSWER", ANSWERABLE_CASES)]:
        for index, case in enumerate(cases, 1):
            answer = extract_answer(ask(session, headers, agent_id, case["query"])).strip()
            failures = check_case(answer, case["must"], case["forbid"])
            print(f"\n===== {label} {index}. {case['query']} =====")
            print(f"failures={failures}")
            print(answer[:1600])
            if failures:
                failed = True

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
