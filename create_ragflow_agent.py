import base64
import json
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


BASE = "http://localhost"
EMAIL = "school-ragflow@local.test"
PASSWORD = "SchoolRAGFlow2026!"
PUBLIC_KEY = Path(r"C:\Users\wangl\ragflow\conf\public.pem")
PROMPT_FILE = Path(r"C:\Users\wangl\School\ragflow_agent_system_prompt.md")

MAIN_DATASET_ID = "6d7f7b5c632b11f1b64ce5947e819acd"
FACT_DATASET_ID = "c6483a66632c11f1b64ce5947e819acd"
AGENT_TITLE = "南京邮电大学推免政策助手 v1"


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


def build_dsl() -> dict:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    return {
        "components": {
            "begin": {
                "obj": {"component_name": "Begin", "params": {"prologue": "你好，我可以帮你查询南京邮电大学推免/保研政策。"}},
                "downstream": ["Retrieval:FactCards", "Retrieval:MainPolicies"],
                "upstream": [],
            },
            "Retrieval:FactCards": {
                "obj": {
                    "component_name": "Retrieval",
                    "params": {
                        "similarity_threshold": 0.0,
                        "keywords_similarity_weight": 0.7,
                        "top_n": 5,
                        "top_k": 16,
                        "rerank_id": "gte-rerank-v2",
                        "empty_response": "事实卡知识库未检索到明确依据。",
                        "kb_ids": [FACT_DATASET_ID],
                        "query": "{sys.query}",
                    },
                },
                "downstream": ["LLM:PolicyAnswer"],
                "upstream": ["begin"],
            },
            "Retrieval:MainPolicies": {
                "obj": {
                    "component_name": "Retrieval",
                    "params": {
                        "similarity_threshold": 0.0,
                        "keywords_similarity_weight": 0.7,
                        "top_n": 8,
                        "top_k": 48,
                        "rerank_id": "gte-rerank-v2",
                        "empty_response": "主知识库未检索到明确依据。",
                        "kb_ids": [MAIN_DATASET_ID],
                        "query": "{sys.query}",
                    },
                },
                "downstream": ["LLM:PolicyAnswer"],
                "upstream": ["begin"],
            },
            "LLM:PolicyAnswer": {
                "obj": {
                    "component_name": "LLM",
                    "params": {
                        "llm_id": "deepseek-v4-flash@DeepSeek",
                        "sys_prompt": prompt,
                        "prompts": [
                            {
                                "role": "user",
                                "content": "只输出最终答案。必须以“答案：”开头，按“答案/依据/适用范围/提醒”组织。若用户问题包含“推断、估计、猜测、差不多、按往年、帮我补全”，第一句必须写“答案：不能推断”或“答案：不能推断未明确部分”。用户问题：{sys.query}",
                            }
                        ],
                        "temperature": 0.1,
                        "top_p": 0.3,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "max_tokens": 2048,
                        "cite": True,
                    },
                },
                "downstream": ["Message:Reply"],
                "upstream": ["Retrieval:FactCards", "Retrieval:MainPolicies"],
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


def create_or_update_agent(session: requests.Session, headers: dict) -> str:
    dsl = build_dsl()
    list_response = session.get(
        f"{BASE}/api/v1/agents",
        headers=headers,
        params={"page": 1, "page_size": 30, "title": AGENT_TITLE},
        timeout=30,
    )
    list_response.raise_for_status()
    data = list_response.json().get("data", {})
    agents = data.get("canvas", data if isinstance(data, list) else [])
    existing = next((agent for agent in agents if agent.get("title") == AGENT_TITLE), None)
    body = {"title": AGENT_TITLE, "description": "两段检索：事实卡优先，主知识库补充；使用 DeepSeek v4 Flash 与 gte-rerank-v2。", "dsl": dsl}
    if existing:
        agent_id = existing["id"]
        response = session.put(f"{BASE}/api/v1/agents/{agent_id}", headers=headers, json=body, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(payload)
        return agent_id

    response = session.post(f"{BASE}/api/v1/agents", headers=headers, json=body, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(payload)
    list_response = session.get(
        f"{BASE}/api/v1/agents",
        headers=headers,
        params={"page": 1, "page_size": 30, "title": AGENT_TITLE},
        timeout=30,
    )
    list_response.raise_for_status()
    data = list_response.json().get("data", {})
    agents = data.get("canvas", data if isinstance(data, list) else [])
    created = next((agent for agent in agents if agent.get("title") == AGENT_TITLE), None)
    if not created:
        raise RuntimeError("Agent was created but could not be found by title.")
    return created["id"]


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
    agent_id = create_or_update_agent(session, headers)
    print(json.dumps({"agent_id": agent_id, "title": AGENT_TITLE}, ensure_ascii=False))
    tests = [
        "2026届推免申请条件有哪些？",
        "2026届推免名额是多少？",
        "通信学院接收推免的邮箱是什么？",
        "自动化学院复试时间是什么时候？",
    ]
    for query in tests:
        result = ask(session, headers, agent_id, query)
        answer = extract_answer(result)
        print("\n### QUERY:", query)
        print(str(answer)[:1200])


if __name__ == "__main__":
    main()
