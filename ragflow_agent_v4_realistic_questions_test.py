from __future__ import annotations

from create_ragflow_agent_v4 import ask, create_or_update_agent, extract_answer, login


CASES = [
    {
        "query": "085400电子信息推免可以报哪些学院？",
        "must": ["通信与信息工程学院", "物联网学院", "自动化学院", "理学院", "接收端"],
        "must_any": [["8个", "八个", "上述"]],
        "forbid": ["2025届录取数据", "只能报"],
    },
    {
        "query": "我本科不是通信专业，可以申请通信学院电子信息吗？",
        "must": ["本科所学专业", "申请专业相近", "接收端"],
        "forbid": ["肯定可以", "不能申请"],
    },
    {
        "query": "教育科学与技术学院接收推免对英语有要求吗？",
        "must": ["未", "接收端"],
        "must_any": [["明确", "写明", "明示"]],
        "forbid": ["CET-6不低于425", "CET-4不低于425", "推荐端英语要求"],
    },
    {
        "query": "自动化学院和人工智能学院是一起复试吗？",
        "must": ["不是", "分开", "人工智能学院"],
        "forbid": ["同一学院"],
    },
    {
        "query": "社会工作学院和社会与人口学院是一个吗？",
        "must": ["社会与人口学院", "社会工作学院"],
        "must_any": [["是", "统一名称", "同一"]],
        "forbid": ["不是", "两个独立学院"],
    },
    {
        "query": "波特兰学院2026届有推免政策吗？",
        "must": ["未收录", "2025届", "历史"],
        "forbid": ["2026届现行政策如下", "可以按2025届"],
    },
    {
        "query": "马克思主义学院复试是哪天？",
        "must": ["后续通知", "接收端"],
        "forbid": ["9月24日", "9月25日", "9月26日"],
    },
    {
        "query": "材料学院材料邮箱是学院细则原文直接写出来的吗？",
        "must": ["不是", "iammzhang@njupt.edu.cn", "来源为研招网培养单位联系方式"],
        "forbid": ["是的", "细则原文直接写明"],
    },
]


def check_case(answer: str, case: dict) -> list[str]:
    failures: list[str] = []
    if not answer.startswith("答案："):
        failures.append("answer does not start with 答案：")
    for label in ["依据：", "适用范围：", "提醒："]:
        if label not in answer:
            failures.append(f"required section missing: {label}")
    for marker in case.get("must", []):
        if marker not in answer:
            failures.append(f"required marker missing: {marker}")
    for group in case.get("must_any", []):
        if not any(marker in answer for marker in group):
            failures.append(f"one of required markers missing: {group}")
    for marker in case.get("forbid", []):
        if marker in answer:
            failures.append(f"forbidden marker found: {marker}")
    return failures


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")

    failed = False
    for index, case in enumerate(CASES, 1):
        result = ask(session, headers, agent_id, case["query"])
        answer = extract_answer(result).strip()
        failures = check_case(answer, case)
        print(f"\n===== REALISTIC {index}. {case['query']} =====")
        print(f"failures={failures}")
        print(answer[:1800])
        failed |= bool(failures)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
