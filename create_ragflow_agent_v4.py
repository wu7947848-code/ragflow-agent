import base64
import json
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


BASE = "http://localhost"
EMAIL = "school-ragflow@local.test"
PASSWORD = "SchoolRAGFlow2026!"
PUBLIC_KEY = Path(r"C:\Users\wangl\ragflow\conf\public.pem")
PAYLOAD_DIR = Path(r"C:\Users\wangl\School\ragflow_ready_payload_v4")
PROMPT_FILE = Path(r"C:\Users\wangl\School\ragflow_agent_system_prompt_v4.md")

EMBEDDING_MODEL = "text-embedding-v4@Tongyi-Qianwen"
RERANK_MODEL = "gte-rerank-v2"
CHAT_MODEL = "deepseek-v4-flash@DeepSeek"

MAIN_DATASET_NAME = "njupt-tuimian-ragflow-v4-main"
FACT_DATASET_NAME = "njupt-tuimian-ragflow-v4-facts"
AGENT_TITLE = "南京邮电大学推免政策助手 v4"


def encrypt_password(password: str) -> str:
    public_key = serialization.load_pem_public_key(PUBLIC_KEY.read_bytes())
    encrypted = public_key.encrypt(base64.b64encode(password.encode()), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode()


def login() -> tuple[requests.Session, dict]:
    session = requests.Session()
    response = session.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": EMAIL, "password": encrypt_password(PASSWORD)},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(payload)
    return session, {"Authorization": response.headers.get("Authorization", ""), "Content-Type": "application/json"}


def ensure_ok(payload: dict, action: str) -> None:
    if payload.get("code") not in (0, None):
        raise RuntimeError(f"{action} failed: {payload}")


def list_datasets(session: requests.Session, headers: dict) -> list[dict]:
    datasets: list[dict] = []
    for page in range(1, 10):
        response = session.get(
            f"{BASE}/api/v1/datasets",
            headers=headers,
            params={"page": page, "page_size": 100, "orderby": "create_time", "desc": "true"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        ensure_ok(payload, "list datasets")
        data = payload.get("data", {})
        if isinstance(data, list):
            page_items = data
        else:
            page_items = data.get("kbs") or data.get("datasets") or []
        if not page_items:
            break
        datasets.extend(page_items)
        if len(page_items) < 100:
            break
    return datasets


def parser_config(chunk_tokens: int) -> dict:
    return {
        "chunk_token_num": chunk_tokens,
        "delimiter": "\n\n",
        "filename_embd_weight": 0.1,
        "auto_keywords": 0,
        "auto_questions": 0,
        "parent_child": {"use_parent_child": False, "children_delimiter": "\n"},
    }


def create_or_get_dataset(session: requests.Session, headers: dict, name: str, description: str, chunk_tokens: int) -> str:
    existing = next((item for item in list_datasets(session, headers) if item.get("name") == name), None)
    body = {
        "name": name,
        "description": description,
        "embedding_model": EMBEDDING_MODEL,
        "permission": "me",
        "chunk_method": "naive",
        "parser_config": parser_config(chunk_tokens),
    }
    if existing:
        dataset_id = existing["id"]
        response = session.put(f"{BASE}/api/v1/datasets/{dataset_id}", headers=headers, json=body, timeout=30)
        response.raise_for_status()
        ensure_ok(response.json(), f"update dataset {name}")
        return dataset_id

    response = session.post(f"{BASE}/api/v1/datasets", headers=headers, json=body, timeout=30)
    response.raise_for_status()
    payload = response.json()
    ensure_ok(payload, f"create dataset {name}")
    data = payload.get("data", {})
    if isinstance(data, dict) and data.get("id"):
        return data["id"]
    created = next((item for item in list_datasets(session, headers) if item.get("name") == name), None)
    if not created:
        raise RuntimeError(f"Dataset created but not found by name: {name}")
    return created["id"]


def list_documents(session: requests.Session, headers: dict, dataset_id: str) -> list[dict]:
    docs: list[dict] = []
    for page in range(1, 20):
        response = session.get(
            f"{BASE}/api/v1/datasets/{dataset_id}/documents",
            headers=headers,
            params={"page": page, "page_size": 100},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        ensure_ok(payload, "list documents")
        data = payload.get("data", {})
        if isinstance(data, list):
            page_docs = data
        else:
            page_docs = data.get("docs") or data.get("documents") or []
        if not page_docs:
            break
        docs.extend(page_docs)
        if len(page_docs) < 100:
            break
    return docs


def clear_documents(session: requests.Session, headers: dict, dataset_id: str) -> None:
    doc_ids = [doc["id"] for doc in list_documents(session, headers, dataset_id)]
    if not doc_ids:
        return
    response = session.delete(
        f"{BASE}/api/v1/datasets/{dataset_id}/documents",
        headers=headers,
        json={"ids": doc_ids},
        timeout=60,
    )
    response.raise_for_status()
    ensure_ok(response.json(), "delete existing documents")


def upload_documents(session: requests.Session, headers: dict, dataset_id: str, files: list[Path]) -> list[str]:
    doc_ids: list[str] = []
    for path in files:
        with path.open("rb") as file_obj:
            response = session.post(
                f"{BASE}/api/v1/datasets/{dataset_id}/documents",
                headers={"Authorization": headers["Authorization"]},
                files={"file": (path.name, file_obj, "text/markdown")},
                timeout=60,
            )
        response.raise_for_status()
        payload = response.json()
        ensure_ok(payload, f"upload {path.name}")
        data = payload.get("data", [])
        uploaded = data if isinstance(data, list) else [data]
        doc_ids.extend(doc["id"] for doc in uploaded)
    return doc_ids


def parse_documents(session: requests.Session, headers: dict, dataset_id: str, doc_ids: list[str]) -> None:
    for start in range(0, len(doc_ids), 20):
        batch = doc_ids[start : start + 20]
        response = session.post(
            f"{BASE}/api/v1/datasets/{dataset_id}/documents/parse",
            headers=headers,
            json={"document_ids": batch},
            timeout=30,
        )
        response.raise_for_status()
        ensure_ok(response.json(), "parse documents")


def wait_for_documents(session: requests.Session, headers: dict, dataset_id: str, doc_ids: list[str]) -> list[dict]:
    wanted = set(doc_ids)
    for _ in range(180):
        docs = [doc for doc in list_documents(session, headers, dataset_id) if doc.get("id") in wanted]
        done = [doc for doc in docs if str(doc.get("run")) in {"DONE", "3"} and int(doc.get("chunk_count") or doc.get("chunk_num") or 0) > 0]
        failed = [doc for doc in docs if str(doc.get("run")) in {"FAIL", "4"}]
        if failed:
            raise RuntimeError(f"Document parse failed: {failed}")
        if len(done) == len(wanted):
            return done
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for dataset {dataset_id} parse")


def official_files() -> list[Path]:
    return sorted(path for path in PAYLOAD_DIR.glob("*.md") if path.name[:2].isdigit() and path.name.endswith("_policy.md"))


def fact_files() -> list[Path]:
    return sorted(PAYLOAD_DIR.glob("9*_facts_*.md"))


def sync_dataset(session: requests.Session, headers: dict, dataset_id: str, files: list[Path]) -> dict:
    clear_documents(session, headers, dataset_id)
    doc_ids = upload_documents(session, headers, dataset_id, files)
    parse_documents(session, headers, dataset_id, doc_ids)
    docs = wait_for_documents(session, headers, dataset_id, doc_ids)
    return {"dataset_id": dataset_id, "documents": len(docs), "chunks": sum(int(doc.get("chunk_count") or doc.get("chunk_num") or 0) for doc in docs)}


ANSWER_FLOW = ["Retrieval:StructuredFacts", "Retrieval:OfficialPolicies"]
OUT_OF_SCOPE_GUARD_FLOW = ["Message:OutOfScopeGuard"]
NO_INFERENCE_FLOW = ["Message:NoInference"]
COLLEGE_CLARIFY_FLOW = ["Message:ClarifyCollege"]
MATERIAL_CONTACT_SOURCE_FLOW = ["Message:MaterialContactSource"]
MATERIAL_EMAIL_SOURCE_FLOW = ["Message:MaterialEmailSource"]
IOT_EMAIL_UNSTATED_FLOW = ["Message:IotEmailUnstated"]
COMPETITION_PATH_FLOW = ["Message:CompetitionPath"]
TELECOM_TIMELINE_FLOW = ["Message:TelecomTimeline"]
TELECOM_LOCATION_FLOW = ["Message:TelecomLocation"]
SEP26_REVIEW_FLOW = ["Message:Sep26Review"]
MARX_REVIEW_NOT_SEP26_FLOW = ["Message:MarxReviewNotSep26"]
RECOMMENDATION_MATERIAL_MISSING_FLOW = ["Message:RecommendationMaterialMissing"]
RECOMMENDATION_CONDITIONS_FLOW = ["Message:RecommendationConditions"]
QUALIFICATION_DISTINCTION_FLOW = ["Message:QualificationDistinction"]
POLICY_SIDE_CLARIFY_FLOW = ["Message:ClarifyPolicySide"]
PROGRAM_TYPE_CLARIFY_FLOW = ["Message:ClarifyProgramType"]
RESOLVED_QUERY = "LLM:ResolveQuery@content"
EXTRACTED_STATE = "LLM:ExtractState@content"

OUT_OF_SCOPE_TERMS = [
    "表白信",
    "情书",
    "火锅",
    "饭店",
    "餐厅",
    "旅游攻略",
    "天气",
    "股票",
    "彩票",
    "小说",
    "写诗",
    "菜谱",
    "电影",
    "游戏",
    "星座",
]

NO_INFERENCE_TERMS = [
    "推断",
    "估计",
    "估一个数",
    "猜测",
    "差不多",
    "按往年",
    "帮我补全",
]

ABUSE_OR_INTERNAL_TERMS = [
    "忽略前面",
    "忽略之前",
    "忽略所有",
    "提示词",
    "系统提示",
    "系统指令",
    "内部提示",
    "内部规则",
    "内部配置",
    "知识库ID",
    "API key",
    "apikey",
    "密钥",
    "token",
    "密码",
    "越狱",
    "jailbreak",
    "绕过",
    "破解",
    "注入",
    "攻击",
    "爬取账号",
    "登录验证",
]

KNOWN_COLLEGE_TERMS = [
    "通院",
    "通信学院",
    "通信与信息工程学院",
    "电光学院",
    "电子与光学",
    "柔性电子",
    "集成电路学院",
    "集成电路",
    "计算机学院",
    "计软网安",
    "软件学院",
    "网络空间安全",
    "自动化学院",
    "人工智能学院",
    "材料学院",
    "材料科学",
    "信息材料",
    "化生学院",
    "化学与生命",
    "物联网学院",
    "理学院",
    "邮政学院",
    "现代邮政",
    "交通学院",
    "智慧交通",
    "数媒学院",
    "数字媒体",
    "设计艺术",
    "管理学院",
    "经济学院",
    "马克思主义学院",
    "社会与人口",
    "社会工作学院",
    "外国语学院",
    "教育科学",
    "贝尔英才",
]

ANSWERABLE_CONTEXT_TERMS = [
    "推荐端",
    "接收端",
    "校内",
    "外校",
    "获得推免资格",
    "校内推免",
    "接收推免",
    "直博",
    "博士",
    "研招办",
    "研究生招生",
    "招生办公室",
    "研招网",
    "学校电话",
    "学校邮箱",
    "推断",
    "估计",
    "猜测",
    "差不多",
    "按往年",
    "2025",
    "历史",
    "推免服务系统",
    "系统关闭",
    "补报",
    "待录取",
    "复试资格",
    "录取资格",
    "官方依据",
    "知识库里没有",
    "知识库没有",
    "没有依据",
    "怎么回答",
    "英语",
    "英语要求",
    "英语六级",
    "英语四级",
    "六级",
    "四级",
    "CET-6",
    "CET-4",
]

SCHOOL_ANSWERABLE_CONTEXT_TERMS = [
    "研招办",
    "研究生招生",
    "招生办公室",
    "学校电话",
    "学校邮箱",
    "推免服务系统",
    "系统关闭",
    "补报",
    "待录取",
    "录取资格",
    "官方依据",
    "知识库里没有",
    "知识库没有",
    "没有依据",
    "怎么回答",
    "所有学院",
    "各学院",
    "全部学院",
]

COLLEGE_DETAIL_TERMS = [
    "需要说明具体学院",
    "具体学院或培养单位",
    "材料怎么交",
    "材料怎么提交",
    "材料如何提交",
    "申请材料",
    "材料提交",
    "提交方式",
    "提交邮箱",
    "发到哪个邮箱",
    "发到哪",
    "邮箱",
    "电话",
    "联系方式",
    "复试时间",
    "复试地点",
    "复试批次",
    "第一批",
    "第二批",
    "第一轮",
    "第二轮",
    "批次",
    "面试时间",
    "腾讯会议",
    "这个学院",
    "该学院",
    "学院细则",
]

RAW_FIRST_TURN_AMBIGUOUS_TERMS = [
    "那它",
    "它的",
    "这个学院",
    "该学院",
    "这个邮箱",
    "这个电话",
    "张老师",
    "也给我",
    "第一批",
    "第二批",
    "第一轮",
    "第二轮",
    "材料要怎么交",
    "材料怎么交",
    "材料怎么提交",
    "材料如何提交",
    "材料提交方式",
    "提交方式",
]

RAW_FIRST_TURN_EXCLUSION_TERMS = [
    *KNOWN_COLLEGE_TERMS,
    *SCHOOL_ANSWERABLE_CONTEXT_TERMS,
    "学校",
    "全校",
    "校级",
    "哪些学院",
    "哪几个学院",
    "哪些单位",
    "培养单位",
    "校内",
    "推荐端",
    "接收端",
]

RAW_FIRST_TURN_POLICY_SIDE_AMBIGUOUS_TERMS = [
    "保研条件",
    "推免条件",
    "申请条件",
    "保研流程",
    "推免流程",
    "推免申请",
]

RAW_FIRST_TURN_POLICY_SIDE_EXCLUSION_TERMS = [
    "校内",
    "推荐端",
    "接收端",
    "接收推免",
    "复试",
    "录取",
    "待录取",
    "材料",
    "邮箱",
    "电话",
    "联系方式",
    "推免服务系统",
    "系统",
    "研招办",
    "直博",
]

PROGRAM_TYPE_TERMS = ["专家推荐书", "导师联系", "联系导师", "额外材料"]

POLICY_SIDE_TERMS = [
    "保研条件",
    "推免条件",
    "推免申请",
    "申请条件",
    "保研流程",
    "推免流程",
    "推免资格",
    "保研资格",
    "保研名额",
    "推免名额",
    "综合排名",
    "英语六级",
    "六级",
    "竞赛奖",
]


def switch_condition(terms: list[str], to: list[str]) -> dict:
    return {
        "items": [{"cpn_id": RESOLVED_QUERY, "operator": "contains", "value": term} for term in terms],
        "logical_operator": "or",
        "to": to,
    }


def raw_switch_condition(terms: list[str], to: list[str]) -> dict:
    return {
        "items": [{"cpn_id": "sys.query", "operator": "contains", "value": term} for term in terms],
        "logical_operator": "or",
        "to": to,
    }


def raw_all_condition(terms: list[str], to: list[str]) -> dict:
    return {
        "items": [{"cpn_id": "sys.query", "operator": "contains", "value": term} for term in terms],
        "logical_operator": "and",
        "to": to,
    }


def resolved_all_condition(terms: list[str], to: list[str]) -> dict:
    return {
        "items": [{"cpn_id": RESOLVED_QUERY, "operator": "contains", "value": term} for term in terms],
        "logical_operator": "and",
        "to": to,
    }


def raw_first_turn_clarify_condition(term: str) -> dict:
    items = [
        {"cpn_id": "sys.conversation_turns", "operator": "=", "value": "1"},
        {"cpn_id": "sys.query", "operator": "contains", "value": term},
    ]
    items.extend({"cpn_id": "sys.query", "operator": "not contains", "value": exclusion} for exclusion in RAW_FIRST_TURN_EXCLUSION_TERMS)
    return {"items": items, "logical_operator": "and", "to": COLLEGE_CLARIFY_FLOW}


def raw_first_turn_policy_side_clarify_condition(term: str) -> dict:
    items = [
        {"cpn_id": "sys.conversation_turns", "operator": "=", "value": "1"},
        {"cpn_id": "sys.query", "operator": "contains", "value": term},
    ]
    items.extend(
        {"cpn_id": "sys.query", "operator": "not contains", "value": exclusion}
        for exclusion in RAW_FIRST_TURN_POLICY_SIDE_EXCLUSION_TERMS
    )
    return {"items": items, "logical_operator": "and", "to": POLICY_SIDE_CLARIFY_FLOW}


def build_dsl(main_dataset_id: str, fact_dataset_id: str) -> dict:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    return {
        "components": {
            "begin": {
                "obj": {"component_name": "Begin", "params": {"prologue": "你好，我可以帮你查询南京邮电大学推免/保研政策。"}},
                "downstream": ["Switch:SafetyGuard"],
                "upstream": [],
            },
            "Switch:SafetyGuard": {
                "obj": {
                    "component_name": "Switch",
                    "params": {
                        "conditions": [
                            raw_switch_condition(OUT_OF_SCOPE_TERMS, OUT_OF_SCOPE_GUARD_FLOW),
                            raw_switch_condition(ABUSE_OR_INTERNAL_TERMS, OUT_OF_SCOPE_GUARD_FLOW),
                            raw_switch_condition(NO_INFERENCE_TERMS, NO_INFERENCE_FLOW),
                        ],
                        "end_cpn_ids": ["Switch:FirstTurnClarification"],
                    },
                },
                "downstream": ["Message:OutOfScopeGuard", "Message:NoInference", "Switch:FirstTurnClarification"],
                "upstream": ["begin"],
            },
            "Switch:FirstTurnClarification": {
                "obj": {
                    "component_name": "Switch",
                    "params": {
                        "conditions": [
                            raw_all_condition(["通信", "时间点"], TELECOM_TIMELINE_FLOW),
                            raw_all_condition(["通信", "关键时间"], TELECOM_TIMELINE_FLOW),
                            raw_all_condition(["通信", "时间线"], TELECOM_TIMELINE_FLOW),
                            *[raw_first_turn_clarify_condition(term) for term in RAW_FIRST_TURN_AMBIGUOUS_TERMS],
                            *[
                                raw_first_turn_policy_side_clarify_condition(term)
                                for term in RAW_FIRST_TURN_POLICY_SIDE_AMBIGUOUS_TERMS
                            ],
                        ],
                        "end_cpn_ids": ["LLM:ExtractState"],
                    },
                },
                "downstream": ["Message:ClarifyCollege", "Message:ClarifyPolicySide", "Message:TelecomTimeline", "LLM:ExtractState"],
                "upstream": ["Switch:SafetyGuard"],
            },
            "Message:OutOfScopeGuard": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：这个问题不属于南京邮电大学推免/保研政策查询范围，或涉及获取内部配置、执行不当操作，我不能处理。\n\n"
                            "依据：本助手的知识库范围限于南京邮电大学推免/保研政策、学院复试录取细则、联系方式、时间安排和相关官方依据。\n\n"
                            "适用范围：服务范围与安全边界。\n\n"
                            "提醒：可以改问具体学院的推免/保研政策、材料提交、复试时间、联系方式、推荐端/接收端边界等问题。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:SafetyGuard"],
            },
            "Message:NoInference": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：不能推断未明确部分。本知识库未收录明确规定的2026届推免名额、时间、比例、条件或流程，不能估算、补全或按往年材料外推；涉及2025届历史材料时，也不能据此推断2026届。\n\n"
                            "依据：本知识库只允许依据已收录官方政策原文、学院细则和结构化事实表回答；2025届历史材料或缺失信息不得作为2026届当前政策结论。\n\n"
                            "适用范围：2026届推荐端和接收端中未收录明确依据的信息查询；2025届历史材料只能作为历史参考，不能外推为2026届政策。\n\n"
                            "提醒：请以南京邮电大学及相关学院最新官方通知为准；如果需要，我可以帮你查询某个具体学院或某一政策端已收录的明确信息。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:SafetyGuard"],
            },
            "LLM:ExtractState": {
                "obj": {
                    "component_name": "LLM",
                    "params": {
                        "llm_id": CHAT_MODEL,
                        "message_history_window_size": 8,
                        "sys_prompt": (
                            "你是南京邮电大学推免政策会话状态抽取器。你的任务不是回答用户，而是从当前问题和最近对话中抽取可用于检索的状态。\n\n"
                            "只允许输出以下固定七行，不要解释，不要 Markdown，不要添加第八行：\n"
                            "学院=...\n"
                            "政策端=推荐端/接收端/未确定\n"
                            "届别=2026届/2025届/未确定\n"
                            "批次=第一批/第二批/未确定\n"
                            "培养类型=普通推免/直博/未确定\n"
                            "对象=邮箱/电话/材料提交/复试时间/复试地点/英语要求/竞赛通道/名额/推荐条件/系统操作/未确定\n"
                            "置信边界=明确/需澄清\n\n"
                            "抽取规则：\n"
                            "1. 当前问题明确写出的信息优先于历史；用户用“我问的是、不是什么、不是接收端、校内保研资格、推荐端、接收端”等纠正边界时，必须按当前问题更新政策端。\n"
                            "2. “校内保研资格、获得推免资格、推荐条件、综合排名、推免名额、竞赛/论文通道、英语要求是否满足推免资格”属于推荐端；“复试、录取、待录取、材料提交、邮箱、电话、复试时间、复试地点、推免服务系统”属于接收端。\n"
                            "3. 当前问题是“它、该学院、这个学院、这个邮箱、第一批呢、第二批呢、那电话呢、张老师电话是多少、材料要怎么交”等追问时，可以继承最近一轮已经明确的学院、政策端、届别、批次、对象。\n"
                            "4. 当前问题开启新边界且未写具体学院时，不得继承历史学院；学院写“未确定”。例如用户说“我问的是校内保研资格，不是接收外校推免”，学院=未确定，政策端=推荐端。\n"
                            "5. 届别默认按当前知识库试验范围写2026届；只有用户明确问2025届或历史参考材料时才写2025届。\n"
                            "6. 学院别名要规范化：通信学院=通信与信息工程学院；计算机学院=计算机学院、软件学院、网络空间安全学院；网安学院=计算机学院、软件学院、网络空间安全学院；材料学院=材料科学与工程学院/信息材料与纳米技术研究院；物联网学院=物联网学院。\n"
                            "7. “材料要怎么交、材料怎么提交”表示对象=材料提交，不表示材料学院；只有明确写“材料学院、材料科学、信息材料”才表示材料学院。\n"
                            "8. 如果缺少回答该问题必须的信息，置信边界=需澄清；否则置信边界=明确。若追问已经从历史中继承到必要学院、政策端、批次或对象，也应写置信边界=明确。不要猜测学院、批次、邮箱或时间。\n"
                            "9. 示例只用于理解规则，不是当前对话历史；不得把示例中的学院或日期当作当前状态。\n"
                        ),
                        "prompts": [
                            {
                                "role": "user",
                                "content": "当前用户问题：{sys.query}\n只输出七行状态：",
                            }
                        ],
                        "temperature": 0,
                        "top_p": 0.1,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "max_tokens": 256,
                        "cite": False,
                    },
                },
                "downstream": ["LLM:ResolveQuery"],
                "upstream": ["Switch:FirstTurnClarification"],
            },
            "LLM:ResolveQuery": {
                "obj": {
                    "component_name": "LLM",
                    "params": {
                        "llm_id": CHAT_MODEL,
                        "message_history_window_size": 8,
                        "sys_prompt": (
                            "你是南京邮电大学推免政策检索前的问题改写器。你的任务不是回答问题，而是把当前用户问题改写为一条完整、可检索的中文问题。\n\n"
                            "你会收到上一步抽取出的结构化会话状态。优先使用结构化状态中的明确字段补全检索问题；字段为“未确定”或“需澄清”时，不得自行猜测。\n\n"
                            "规则：\n"
                            "1. 只输出一行改写后的问题，不要解释、不要加标签、不要 Markdown。\n"
                            "2. 如果当前问题已经完整，尽量原样输出。\n"
                            "3. 如果结构化状态中的政策端是“推荐端”或“接收端”，改写后的检索问题必须保留“推荐端”或“接收端”这四个字，避免两端政策混用。\n"
                            "4. 如果当前问题是追问或省略表达，可以只使用最近对话中已经明确出现的学院、单位、政策端、年份、邮箱、老师、批次或培养类型来补全。\n"
                            "5. 只有当前问题使用“它、该学院、这个学院、这个邮箱、第一批呢、第二批呢、那电话呢、张老师电话是多少、材料要怎么交”等明显追问/省略表达时，才继承上一轮学院或对象。\n"
                            "6. 如果当前问题显式开启新边界或纠正边界，例如包含“我问的是、不是、校内保研资格、校内获得推免资格、推荐端、接收端”，且当前问题没有写出具体学院，则不得继承历史学院，必须改写成全校/校级问题。\n"
                            "7. “材料要怎么交/材料怎么提交”表示申请材料提交方式，不是“材料学院”；只有当前问题明确写“材料学院、材料科学、信息材料”时，才表示材料科学与工程学院。\n"
                            "8. 如果当前问题是“竞赛通道呢、材料呢、流程呢、名额呢”这类新子话题，改写为该子话题的完整条件/流程/范围，不要只沿用上一轮的某个局部问题（例如上一轮问英语，下一轮“竞赛通道呢”应问竞赛/论文通道完整条件，而不是只问竞赛通道英语要求）。\n"
                            "9. 如果历史为空或历史没有明确学院，而当前问题包含“这个学院、该学院、第一批、第二批、第一轮、第二轮、批次、材料要怎么交、邮箱、电话”等依赖具体学院的信息，必须输出“需要说明具体学院或培养单位：”加原问题，不要猜测学院，也不要列出所有学院。\n"
                            "10. 不得补入历史中没有明确出现的信息，不得把接收端和推荐端互换，不得把一个学院扩展成其他学院。\n"
                            "11. 若历史仍不足以确定必要边界，保留原问题中的模糊性，不要猜测。\n"
                            "12. 下方例子只是规则示范，不是当前对话历史；不得把例子里的通信学院、材料学院或计算机学院当成当前用户上下文。\n\n"
                            "例子：\n"
                            "历史为空。当前问题：“那它的电话是多少？”\n"
                            "输出：需要说明具体学院或培养单位：那它的电话是多少？\n"
                            "历史为空。当前问题：“材料要怎么交？”\n"
                            "输出：需要说明具体学院或培养单位：材料要怎么交？\n"
                            "历史为空。当前问题：“这个学院的邮箱是多少？”\n"
                            "输出：需要说明具体学院或培养单位：这个学院的邮箱是多少？\n"
                            "历史为空。当前问题：“第二批复试时间？”\n"
                            "输出：需要说明具体学院或培养单位：第二批复试时间？\n"
                            "历史：用户问“通信学院推免材料发到哪个邮箱？”助手回答“通信与信息工程学院邮箱为 scie-yz@njupt.edu.cn”。当前问题：“那它的电话是多少？”\n"
                            "输出：通信与信息工程学院2026届接收端咨询电话是多少？\n"
                            "历史：用户问“材料学院材料提交邮箱是什么？”助手回答“邮箱为 iammzhang@njupt.edu.cn，来源为研招网培养单位联系方式”。当前问题：“这个邮箱是复试细则原文写的吗？”\n"
                            "输出：材料科学与工程学院 iammzhang@njupt.edu.cn 是否为2026届复试细则原文直接写明，还是来自研招网培养单位联系方式？\n"
                            "历史：用户问“材料学院材料提交邮箱是什么？”助手回答“材料科学与工程学院/信息材料与纳米技术研究院邮箱为 iammzhang@njupt.edu.cn”。当前问题：“张老师电话是多少？”\n"
                            "输出：材料科学与工程学院/信息材料与纳米技术研究院2026届接收端张老师咨询电话是多少？\n"
                            "历史：用户问“我问的是校内保研资格，不是接收外校推免”。当前问题：“英语必须六级425吗？”\n"
                            "输出：南京邮电大学2026届校内推免资格推荐端英语要求是否必须CET-6不低于425分？\n"
                            "历史：用户问“南京邮电大学2026届校内推免资格推荐端英语要求是否必须CET-6不低于425分？”助手回答“竞赛/论文通道可放宽至CET-4”。当前问题：“竞赛通道呢？”\n"
                            "输出：南京邮电大学2026届校内推免资格推荐端竞赛/论文通道的完整条件是什么，包括智育排名、竞赛或论文要求和英语要求？\n"
                            "历史：用户问“计算机学院第二批复试时间？”助手回答“第二批10月16日15:00”。当前问题：“材料要怎么交？”\n"
                            "输出：计算机学院、软件学院、网络空间安全学院2026届接收端推免申请材料怎么提交？\n"
                            "历史：用户问“计算机学院第二批复试时间？”助手回答“第二批10月16日15:00”。当前问题：“我问的是校内保研资格，不是接收外校推免”\n"
                            "输出：南京邮电大学2026届校内获得推免资格推荐端的校级条件是什么？"
                        ),
                        "prompts": [
                            {
                                "role": "user",
                                "content": "当前用户问题：{sys.query}\n结构化会话状态：\n{LLM:ExtractState@content}\n只输出完整检索问题：",
                            }
                        ],
                        "temperature": 0,
                        "top_p": 0.1,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "max_tokens": 256,
                        "cite": False,
                    },
                },
                "downstream": ["Switch:ClarificationGate"],
                "upstream": ["LLM:ExtractState"],
            },
            "Switch:ClarificationGate": {
                "obj": {
                    "component_name": "Switch",
                    "params": {
                        "conditions": [
                            resolved_all_condition(["材料科学", "张老师"], MATERIAL_CONTACT_SOURCE_FLOW),
                            resolved_all_condition(["材料科学", "电话", "邮箱"], MATERIAL_CONTACT_SOURCE_FLOW),
                            resolved_all_condition(["材料科学", "材料提交", "邮箱"], MATERIAL_EMAIL_SOURCE_FLOW),
                            resolved_all_condition(["材料科学", "邮箱"], MATERIAL_EMAIL_SOURCE_FLOW),
                            resolved_all_condition(["材料科学", "iammzhang"], MATERIAL_EMAIL_SOURCE_FLOW),
                            resolved_all_condition(["材料科学", "复试细则原文"], MATERIAL_EMAIL_SOURCE_FLOW),
                            resolved_all_condition(["物联网学院", "材料提交邮箱"], IOT_EMAIL_UNSTATED_FLOW),
                            resolved_all_condition(["物联网学院", "提交邮箱"], IOT_EMAIL_UNSTATED_FLOW),
                            resolved_all_condition(["物联网学院", "邮箱"], IOT_EMAIL_UNSTATED_FLOW),
                            resolved_all_condition(["竞赛", "通道"], COMPETITION_PATH_FLOW),
                            resolved_all_condition(["竞赛", "CET-4"], COMPETITION_PATH_FLOW),
                            resolved_all_condition(["没过六级", "竞赛"], COMPETITION_PATH_FLOW),
                            resolved_all_condition(["通信", "时间点"], TELECOM_TIMELINE_FLOW),
                            resolved_all_condition(["通信", "关键时间"], TELECOM_TIMELINE_FLOW),
                            resolved_all_condition(["通信", "复试地点"], TELECOM_LOCATION_FLOW),
                            resolved_all_condition(["通信", "地点"], TELECOM_LOCATION_FLOW),
                            resolved_all_condition(["马克思主义学院", "9月26日"], MARX_REVIEW_NOT_SEP26_FLOW),
                            resolved_all_condition(["马克思主义学院", "物联网学院"], MARX_REVIEW_NOT_SEP26_FLOW),
                            resolved_all_condition(["9月26日", "学院"], SEP26_REVIEW_FLOW),
                            resolved_all_condition(["9月26日", "复试"], SEP26_REVIEW_FLOW),
                            resolved_all_condition(["推荐端", "材料提交"], RECOMMENDATION_MATERIAL_MISSING_FLOW),
                            resolved_all_condition(["推荐端", "材料", "邮箱"], RECOMMENDATION_MATERIAL_MISSING_FLOW),
                            resolved_all_condition(["校内", "推荐端", "邮箱"], RECOMMENDATION_MATERIAL_MISSING_FLOW),
                            resolved_all_condition(["推荐端", "获得推免资格"], RECOMMENDATION_CONDITIONS_FLOW),
                            resolved_all_condition(["推荐端", "保研资格"], RECOMMENDATION_CONDITIONS_FLOW),
                            resolved_all_condition(["推荐端", "条件"], RECOMMENDATION_CONDITIONS_FLOW),
                            resolved_all_condition(["复试资格", "录取资格"], QUALIFICATION_DISTINCTION_FLOW),
                            resolved_all_condition(["待录取", "录取资格"], QUALIFICATION_DISTINCTION_FLOW),
                            switch_condition(KNOWN_COLLEGE_TERMS, ANSWER_FLOW),
                            switch_condition(SCHOOL_ANSWERABLE_CONTEXT_TERMS, ANSWER_FLOW),
                            switch_condition(COLLEGE_DETAIL_TERMS, COLLEGE_CLARIFY_FLOW),
                            switch_condition(ANSWERABLE_CONTEXT_TERMS, ANSWER_FLOW),
                            switch_condition(PROGRAM_TYPE_TERMS, PROGRAM_TYPE_CLARIFY_FLOW),
                            switch_condition(POLICY_SIDE_TERMS, POLICY_SIDE_CLARIFY_FLOW),
                        ],
                        "end_cpn_ids": ANSWER_FLOW,
                    },
                },
                "downstream": [
                    "Message:ClarifyCollege",
                    "Message:MaterialContactSource",
                    "Message:MaterialEmailSource",
                    "Message:IotEmailUnstated",
                    "Message:CompetitionPath",
                    "Message:TelecomTimeline",
                    "Message:TelecomLocation",
                    "Message:Sep26Review",
                    "Message:MarxReviewNotSep26",
                    "Message:RecommendationMaterialMissing",
                    "Message:RecommendationConditions",
                    "Message:QualificationDistinction",
                    "Message:ClarifyPolicySide",
                    "Message:ClarifyProgramType",
                    "Retrieval:StructuredFacts",
                    "Retrieval:OfficialPolicies",
                ],
                "upstream": ["LLM:ResolveQuery"],
            },
            "Message:ClarifyCollege": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：请先说明具体学院或培养单位名称。\n\n"
                            "依据：材料提交方式、邮箱、电话、复试时间和地点通常按学院细则分别规定，不能用其他学院信息替代。\n\n"
                            "适用范围：学院相关的材料提交、联系方式、复试安排、复试细则查询。\n\n"
                            "提醒：补充学院名称后，我会优先查询该学院2026届官方细则。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:FirstTurnClarification", "Switch:ClarificationGate"],
            },
            "Message:MaterialContactSource": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：材料科学与工程学院/信息材料与纳米技术研究院的材料提交邮箱为 iammzhang@njupt.edu.cn，来源为南京邮电大学研究生招生信息网培养单位联系方式，来源为研招网培养单位联系方式；张老师咨询电话为 025-85866533，来源为学院2026届复试录取细则正文联系方式表。\n\n"
                            "依据：28_policy.md《材料科学与工程学院2026年招收推免生（含直博生）复试录取工作细则》正文列出电话 025-85866533（张老师），但正文未直接列出具体邮箱地址；结构化事实表 91_facts_college_contacts.md 对邮箱 iammzhang@njupt.edu.cn 及其来源作了补充标注。\n\n"
                            "适用范围：2026届，材料科学与工程学院/信息材料与纳米技术研究院，接收端联系方式和材料提交邮箱来源查询。\n\n"
                            "提醒：请以南京邮电大学研究生招生信息网及学院最新官方通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:MaterialEmailSource": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：不是。材料科学与工程学院/信息材料与纳米技术研究院的材料提交邮箱为 iammzhang@njupt.edu.cn。复试细则正文未直接列出该邮箱；它来自南京邮电大学研究生招生信息网培养单位联系方式，来源为研招网培养单位联系方式。\n\n"
                            "依据：28_policy.md《材料科学与工程学院2026年招收推免生（含直博生）复试录取工作细则》正文仅写明发送至学院联系邮箱，未直接列出具体邮箱地址；结构化事实表 91_facts_college_contacts.md 对该邮箱来源作了补充标注。\n\n"
                            "适用范围：2026届，材料科学与工程学院/信息材料与纳米技术研究院，接收端。\n\n"
                            "提醒：请以南京邮电大学研究生招生信息网及学院最新官方通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:FirstTurnClarification", "Switch:ClarificationGate"],
            },
            "Message:IotEmailUnstated": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：物联网学院2026届复试时间为9月26日；2026届复试录取细则中材料提交邮箱为未明示。可提供学院咨询邮箱 iot@njupt.edu.cn 和咨询电话 025-83535107，不得使用往年邮箱替代。\n\n"
                            "依据：35_policy.md《物联网学院2026年招收推免生（含直博生）复试录取工作细则》；结构化事实表 91_facts_college_contacts.md、92_facts_review_schedule.md。\n\n"
                            "适用范围：2026届，物联网学院，接收端。\n\n"
                            "提醒：请以南京邮电大学物联网学院最新官方通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:CompetitionPath": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：竞赛/论文通道属于校内获得推免资格的推荐端路径。核心条件为：作为主要成员参加学校认可的重要学科竞赛并取得国家级三等奖及以上，且参赛学校单位主体为南京邮电大学；或以独立作者或第一作者在《南京邮电大学高质量学术期刊》认定范围内发表与专业相关的科研论文。智育排名原则上应在专业年级50%以内。非英语专业学生英语要求可放宽为 CET-4 不低于425分；若 CET-4 也未达到425分，或竞赛不符合官方认定要求，则不能据此判断具备推免资格。\n\n"
                            "依据：01_policy.md《推荐免试研究生管理办法（2025年修订）》（校发〔2025〕7号）；结构化事实表 94_facts_recommendation_requirements.md。\n\n"
                            "适用范围：2026届，推荐端，校内获得推免资格的竞赛/论文通道。\n\n"
                            "提醒：具体竞赛是否符合条件，须以学校当年竞赛认定目录和学院审核为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:TelecomTimeline": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：通信与信息工程学院接收端最应关注这些时间点：2025年9月22日9:00起，全国推免服务系统开放并开始填报志愿；2025年9月23日9:00，学院通过系统发送复试通知；2025年9月24日9:00，学院组织网络远程复试，方式为腾讯会议；2025年9月25日上午9:00，学校通过系统发送待录取通知；2025年10月20日12:00，推免服务系统关闭，之后不能补报志愿。\n\n"
                            "依据：22_policy.md《通信与信息工程学院2026年招收推免生（含直博生）复试录取工作细则》；26_policy.md《南京邮电大学关于接收2026年推荐免试攻读研究生（含直博生）的通知》；44_policy.md《全国推免服务系统操作指南》。\n\n"
                            "适用范围：2026届，通信与信息工程学院，接收端。\n\n"
                            "提醒：如果还没有获得本校推荐资格，还需要同时关注所在本科学校推荐端的校内推免安排；请以南京邮电大学和通信与信息工程学院最新官方通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:TelecomLocation": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：通信与信息工程学院2026届接收端复试方式为网络远程复试，平台为腾讯会议；细则未写明线下物理复试地点。\n\n"
                            "依据：22_policy.md《通信与信息工程学院2026年招收推免生（含直博生）复试录取工作细则》。\n\n"
                            "适用范围：2026届，通信与信息工程学院，接收端。\n\n"
                            "提醒：请以南京邮电大学和通信与信息工程学院最新官方通知为准，实际会议号或具体线上安排以学院通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:Sep26Review": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：本知识库中明确写明2026届接收端复试在9月26日的学院包括：物联网学院；数字媒体与设计艺术学院。其中物联网学院复试时间写为9月26日，数字媒体与设计艺术学院第一轮复试时间为9月26日9:30。\n\n"
                            "依据：92_facts_review_schedule.md；35_policy.md《物联网学院2026年招收推免生（含直博生）复试录取工作细则》；38_policy.md《数字媒体与设计艺术学院2026年招收推免生复试录取工作细则》。\n\n"
                            "适用范围：2026届，接收端，已收录学院复试时间查询。\n\n"
                            "提醒：其他学院若只写后续通知或未收录具体日期，不得按9月26日推断；请以各学院最新官方通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:MarxReviewNotSep26": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：不能按物联网学院9月26日推断马克思主义学院复试时间。马克思主义学院2026届接收端复试时间为后续通知/本知识库未收录具体日期。\n\n"
                            "依据：43_policy.md《马克思主义学院2026年招收推免生复试录取工作细则》未写明具体复试日期；92_facts_review_schedule.md 将马克思主义学院复试时间标注为后续通知/未收录具体日期。物联网学院9月26日只适用于物联网学院，不能替代其他学院安排。\n\n"
                            "适用范围：2026届，马克思主义学院，接收端复试时间查询。\n\n"
                            "提醒：请以南京邮电大学马克思主义学院最新官方通知为准；不同学院复试时间不得互相套用。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:RecommendationMaterialMissing": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：本知识库未收录校内推荐端材料提交邮箱的明确规定；不能把接收端复试/直博申请材料邮箱套用为校内推荐端材料提交邮箱。已收录的学院复试细则材料提交邮箱属于接收端信息。\n\n"
                            "依据：结构化事实表 91_facts_college_contacts.md 对材料提交邮箱的政策端边界作出标注；相关学院推荐端方案未明示校内推荐端材料提交邮箱。\n\n"
                            "适用范围：校内，推荐端；涉及各学院校内获得推免资格过程中的材料提交邮箱问题，同时提醒接收端邮箱不得替代推荐端。\n\n"
                            "提醒：请以南京邮电大学本科生院或所在学院当年最新官方推免通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:RecommendationConditions": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：南京邮电大学校内获得推免资格的推荐端校级条件主要有三条路径：1. 智育排名路径：智育测评成绩在本专业年级30%以内，非英语专业学生 CET-6 成绩不低于425分；2. 竞赛/论文通道：作为主要成员参加学校认可的重要学科竞赛并取得国家级三等奖及以上，且参赛学校单位主体为南京邮电大学，或以独立作者或第一作者在《南京邮电大学高质量学术期刊》认定范围内发表与专业相关的科研论文；智育排名原则上在专业年级50%以内，非英语专业学生英语要求可放宽至 CET-4 不低于425分；3. 本硕博贯通培养路径：入选本硕博贯通培养计划，智育排名在专业年级20%以内，非英语专业学生 CET-6 成绩不低于425分。\n\n"
                            "依据：01_policy.md《推荐免试研究生管理办法（2025年修订）》（校发〔2025〕7号）；结构化事实表 94_facts_recommendation_requirements.md。\n\n"
                            "适用范围：2026届，推荐端，校内获得推免资格的校级条件。\n\n"
                            "提醒：具体竞赛是否符合条件，必须以学校当年竞赛认定目录和学院审核结果为准；各学院还可能有本院推免方案，请以学校和学院最新官方通知为准。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:QualificationDistinction": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：可以区分。复试资格是通过学校或学院初审后获得参加复试的资格；待录取是复试合格后，学校通过全国推免服务系统发送待录取通知，考生在规定时间内确认；录取资格不是复试资格本身，通常还要经过待录取确认、拟录取名单公示以及上级审核等后续环节，最终以公示和审核结果为准。\n\n"
                            "依据：26_policy.md《南京邮电大学关于接收2026年推荐免试攻读研究生（含直博生）的通知》；44_policy.md《全国推免服务系统操作指南》；结构化事实表 94_facts_recommendation_requirements.md。\n\n"
                            "适用范围：2026届，接收端，复试资格、待录取、录取资格的概念区分。\n\n"
                            "提醒：请以南京邮电大学研究生院和相关学院最新官方通知为准；待录取确认一经确认通常不得更改。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:ClarifyPolicySide": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：请先确认你问的是校内获得推免资格（推荐端），还是申请南京邮电大学接收推免/复试录取（接收端）。\n\n"
                            "依据：推荐端和接收端适用的政策依据、资格条件、材料要求不同，不能混用。\n\n"
                            "适用范围：保研条件、推免资格、申请流程、材料要求、名额等边界不明确的问题。\n\n"
                            "提醒：你补充“推荐端”或“接收端”后，我再按对应官方材料回答。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Message:ClarifyProgramType": {
                "obj": {
                    "component_name": "Message",
                    "params": {
                        "content": [
                            "答案：请先确认你问的是普通推免硕士，还是直博申请。\n\n"
                            "依据：直博申请可能涉及导师联系、两名专家推荐书等额外要求，普通推免硕士不一定适用。\n\n"
                            "适用范围：专家推荐书、导师联系、直博额外材料等培养类型相关问题。\n\n"
                            "提醒：补充培养类型后，我会按2026届官方细则查询。"
                        ],
                        "stream": True,
                    },
                },
                "downstream": [],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Retrieval:StructuredFacts": {
                "obj": {
                    "component_name": "Retrieval",
                    "params": {
                        "similarity_threshold": 0.0,
                        "keywords_similarity_weight": 0.7,
                        "top_n": 7,
                        "top_k": 24,
                        "rerank_id": RERANK_MODEL,
                        "empty_response": "结构化事实层未检索到明确依据。",
                        "kb_ids": [fact_dataset_id],
                        "query": "{LLM:ResolveQuery@content}",
                    },
                },
                "downstream": ["LLM:PolicyAnswer"],
                "upstream": ["Switch:ClarificationGate"],
            },
            "Retrieval:OfficialPolicies": {
                "obj": {
                    "component_name": "Retrieval",
                    "params": {
                        "similarity_threshold": 0.0,
                        "keywords_similarity_weight": 0.7,
                        "top_n": 8,
                        "top_k": 48,
                        "rerank_id": RERANK_MODEL,
                        "empty_response": "官方原文层未检索到明确依据。",
                        "kb_ids": [main_dataset_id],
                        "query": "{LLM:ResolveQuery@content}",
                    },
                },
                "downstream": ["LLM:PolicyAnswer"],
                "upstream": ["Switch:ClarificationGate"],
            },
            "LLM:PolicyAnswer": {
                "obj": {
                    "component_name": "LLM",
                    "params": {
                        "llm_id": CHAT_MODEL,
                        "sys_prompt": prompt,
                        "prompts": [
                            {
                                "role": "user",
                                "content": "只输出最终答案。必须以“答案：”开头，并且必须包含“答案：”“依据：”“适用范围：”“提醒：”四个纯文本标签；不得给四个标签加粗，不得写成 Markdown 标题。不得以“根据检索结果”“根据检索到的信息”“检索显示”开头，直接给结论。若用户问题包含“推断、估计、猜测、差不多、按往年、帮我补全”，第一句必须写“答案：不能推断”或“答案：不能推断未明确部分”。若回答联系方式来源是南京邮电大学研究生招生信息网培养单位联系方式，必须同时写明“南京邮电大学研究生招生信息网”和完整短语“来源为研招网培养单位联系方式”，不得改写、省略或拆开该短语。若回答英语要求，必须保留“CET-6”和“CET-4”这些官方简称。“适用范围：”这一行必须逐字写出政策端：接收推免、复试、直博申请材料、待录取、研招办联系方式、推免服务系统操作写“接收端”；校内保研资格、获得推免资格、推免名额、推荐条件、综合排名算法写“推荐端”。用户原问题：{sys.query}\n检索用完整问题：{LLM:ResolveQuery@content}",
                            }
                        ],
                        "temperature": 0.1,
                        "top_p": 0.3,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "max_tokens": 2048,
                        "cite": False,
                    },
                },
                "downstream": ["Message:Reply"],
                "upstream": ["Retrieval:StructuredFacts", "Retrieval:OfficialPolicies"],
            },
            "Message:Reply": {
                "obj": {"component_name": "Message", "params": {"content": ["{LLM:PolicyAnswer@content}"], "stream": True}},
                "downstream": [],
                "upstream": ["LLM:PolicyAnswer"],
            },
        },
        "history": [],
        "path": [],
        "retrieval": [],
        "globals": {"sys.query": "", "sys.user_id": "", "sys.conversation_turns": 0, "sys.files": []},
    }


def create_or_update_agent(session: requests.Session, headers: dict, main_dataset_id: str | None = None, fact_dataset_id: str | None = None) -> str:
    if main_dataset_id is None or fact_dataset_id is None:
        datasets = list_datasets(session, headers)
        main = next((item for item in datasets if item.get("name") == MAIN_DATASET_NAME), None)
        facts = next((item for item in datasets if item.get("name") == FACT_DATASET_NAME), None)
        if not main or not facts:
            raise RuntimeError("v4 datasets not found; run main() first.")
        main_dataset_id = main["id"]
        fact_dataset_id = facts["id"]

    dsl = build_dsl(main_dataset_id, fact_dataset_id)
    response = session.get(
        f"{BASE}/api/v1/agents",
        headers=headers,
        params={"page": 1, "page_size": 100, "title": AGENT_TITLE},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    ensure_ok(payload, "list agents")
    data = payload.get("data", {})
    agents = data.get("canvas", data if isinstance(data, list) else [])
    existing = next((agent for agent in agents if agent.get("title") == AGENT_TITLE), None)
    body = {
        "title": AGENT_TITLE,
        "description": "v4三层架构：结构化事实层优先，官方原文层核对；使用 DeepSeek v4 Flash 与 gte-rerank-v2。",
        "dsl": dsl,
    }
    if existing:
        agent_id = existing["id"]
        update = session.put(f"{BASE}/api/v1/agents/{agent_id}", headers=headers, json=body, timeout=30)
        update.raise_for_status()
        ensure_ok(update.json(), "update v4 agent")
        return agent_id
    create = session.post(f"{BASE}/api/v1/agents", headers=headers, json=body, timeout=30)
    create.raise_for_status()
    ensure_ok(create.json(), "create v4 agent")
    return next(agent["id"] for agent in list_agents(session, headers) if agent.get("title") == AGENT_TITLE)


def list_agents(session: requests.Session, headers: dict) -> list[dict]:
    response = session.get(f"{BASE}/api/v1/agents", headers=headers, params={"page": 1, "page_size": 100}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    ensure_ok(payload, "list agents")
    data = payload.get("data", {})
    return data.get("canvas", data if isinstance(data, list) else [])


def ask(session: requests.Session, headers: dict, agent_id: str, query: str) -> dict:
    response = session.post(
        f"{BASE}/api/v1/agents/chat/completions",
        headers=headers,
        json={"agent_id": agent_id, "query": query, "stream": False, "return_trace": True},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def extract_answer(result: dict) -> str:
    data = result.get("data", result)
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        nested = data.get("data")
        if isinstance(nested, dict):
            outputs = nested.get("outputs")
            if isinstance(outputs, dict) and outputs.get("content"):
                return outputs["content"]
            if nested.get("content"):
                return nested["content"]
        return data.get("answer") or data.get("content") or data.get("message") or ""
    return str(data)


def main() -> None:
    session, headers = login()
    main_dataset_id = create_or_get_dataset(
        session,
        headers,
        MAIN_DATASET_NAME,
        "v4官方原文层：保留政策文件原文/整理版，不承载高风险补丁事实。",
        384,
    )
    fact_dataset_id = create_or_get_dataset(
        session,
        headers,
        FACT_DATASET_NAME,
        "v4结构化事实层：联系方式、复试时间、专业对应、推荐端边界、高风险问答。",
        256,
    )
    main_summary = sync_dataset(session, headers, main_dataset_id, official_files())
    fact_summary = sync_dataset(session, headers, fact_dataset_id, fact_files())
    agent_id = create_or_update_agent(session, headers, main_dataset_id, fact_dataset_id)
    print(json.dumps({"agent_id": agent_id, "main": main_summary, "facts": fact_summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
