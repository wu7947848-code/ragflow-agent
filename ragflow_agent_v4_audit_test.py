from __future__ import annotations

import re

from create_ragflow_agent_v4 import ask, create_or_update_agent, extract_answer, login


GLOBAL_FORBIDDEN = [
    "系统提示",
    "系统指令",
    "用户问",
    "用户问题",
    "检索策略",
    "结构化事实层ID",
    "官方原文层ID",
    "[ID:",
    "<think>",
    "</think>",
    "志原",
    "代录取",
    "RAGFlow-ready v3",
    "26_policy.md（推免服务系统操作指南",
    "26_policy.md（全国推免服务系统操作指南",
]


CASES = [
    {
        "query": "我家孩子想保研南邮通信学院，现在最应该关注哪几个时间点？",
        "must": ["9月23日", "9:00", "9月24日", "腾讯会议", "10月20日", "12:00"],
        "forbid": ["未收录具体时间", "细则尚未收录具体时间", "外校学生", "推荐免试研究生管理办法", "校发〔2025〕7号"],
    },
    {
        "query": "通信学院校内推荐端材料提交邮箱是什么？",
        "must": ["校内", "推荐端", "未收录", "接收端"],
        "forbid": ["接收外校推免材料"],
    },
    {
        "query": "通信学院接收推免材料发到哪个邮箱？",
        "must": ["scie-yz@njupt.edu.cn", "接收端"],
        "forbid": ["可用于校内推荐端", "作为校内推荐端材料提交邮箱"],
    },
    {
        "query": "我想问校内获得推免资格的条件，不是接收外校推免，知识库里有吗？",
        "must": ["推荐端", "学校认可的重要学科竞赛", "国家级三等奖"],
        "forbid": ["学校竞赛分类目录中的A/B/C类赛事", "A/B/C类赛事", "A/B/C类均可", "C类可满足资格"],
    },
    {
        "query": "2025年的推免名额能不能推断2026届也差不多？",
        "must": ["不能推断", "2025届", "2026届"],
        "forbid": ["可以参考为2026届", "大概"],
    },
    {
        "query": "如果我没过六级，但是有竞赛奖，还能走校内推免吗？",
        "must": ["CET-4", "425", "学校认可", "学院审核"],
        "forbid": ["A/B/C类均可", "C类可满足资格", "C类竞赛可满足推免资格", "仅有过六级"],
    },
    {
        "query": "物联网学院2026届复试时间和材料提交邮箱是什么？",
        "must": ["9月26日", "未明示", "iot@njupt.edu.cn", "025-83535107"],
        "forbid": ["fangw@njupt.edu.cn", "参考往年通知"],
    },
    {
        "query": "如果知识库里没有官方依据，你会怎么回答？",
        "must": ["本知识库未收录明确规定", "最新官方通知"],
        "forbid": ["系统提示", "系统规则", "内部规则"],
    },
    {
        "query": "推免服务系统关闭后还能补报志愿吗？",
        "must": ["不能", "10月20日", "12:00", "志愿"],
        "forbid": ["志原", "可以补报"],
    },
    {
        "query": "我问的是录取资格，不是复试资格，能不能区分一下？",
        "must": ["复试资格", "录取资格", "待录取", "公示"],
        "forbid": ["结构化事实表（ID", "官方原文层ID", "ID:", "推荐端与接收端通用"],
    },
]


def check_answer(query: str, answer: str, must: list[str], forbid: list[str]) -> list[str]:
    failures: list[str] = []
    for marker in GLOBAL_FORBIDDEN + forbid:
        if marker and marker in answer:
            failures.append(f"forbidden marker found: {marker}")
    for marker in must:
        if marker not in answer:
            failures.append(f"required marker missing: {marker}")
    if re.search(r"\bID:\d+|\[ID:\d+\]", answer):
        failures.append("internal retrieval ID leaked")
    if not answer.startswith("答案："):
        failures.append("answer does not start with 答案：")
    for label in ["依据：", "适用范围：", "提醒："]:
        if label not in answer:
            failures.append(f"required section missing: {label}")
    return failures


def main() -> None:
    session, headers = login()
    agent_id = create_or_update_agent(session, headers)
    print(f"agent_id={agent_id}")
    failed = False
    for index, case in enumerate(CASES, 1):
        answer = extract_answer(ask(session, headers, agent_id, case["query"])).strip()
        failures = check_answer(case["query"], answer, case["must"], case["forbid"])
        print(f"\n===== AUDIT {index}. {case['query']} =====")
        print(f"failures={failures}")
        print(answer[:1600])
        if failures:
            failed = True
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
