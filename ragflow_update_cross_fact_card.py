import time
from pathlib import Path

from create_ragflow_agent import MAIN_DATASET_ID, BASE, create_or_update_agent, login


FACT_CARD = Path(r"C:\Users\wangl\School\ragflow_ready_payload_v3\98_cross_query_fact_cards.md")


def ensure_ok(payload: dict, action: str) -> None:
    if payload.get("code") not in (0, None):
        raise RuntimeError(f"{action} failed: {payload}")


def list_documents(session, headers):
    response = session.get(
        f"{BASE}/api/v1/datasets/{MAIN_DATASET_ID}/documents",
        headers=headers,
        params={"page": 1, "page_size": 200},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    ensure_ok(payload, "list documents")
    data = payload.get("data", {})
    if isinstance(data, list):
        docs = data
    else:
        docs = data.get("docs") or data.get("documents") or []
    return docs


def find_cross_fact_docs(session, headers):
    return [doc for doc in list_documents(session, headers) if str(doc.get("name", "")).startswith("98_cross_query_fact_cards")]


def delete_documents(session, headers, doc_ids):
    if not doc_ids:
        return
    response = session.delete(
        f"{BASE}/api/v1/datasets/{MAIN_DATASET_ID}/documents",
        headers=headers,
        json={"ids": doc_ids},
        timeout=30,
    )
    response.raise_for_status()
    ensure_ok(response.json(), "delete old cross fact card")


def upload_document(session, headers):
    auth_headers = {"Authorization": headers["Authorization"]}
    with FACT_CARD.open("rb") as file_obj:
        response = session.post(
            f"{BASE}/api/v1/datasets/{MAIN_DATASET_ID}/documents",
            headers=auth_headers,
            files={"file": (FACT_CARD.name, file_obj, "text/markdown")},
            timeout=60,
        )
    response.raise_for_status()
    payload = response.json()
    ensure_ok(payload, "upload cross fact card")
    data = payload.get("data", [])
    docs = data if isinstance(data, list) else [data]
    doc_id = docs[0]["id"]
    return doc_id


def parse_document(session, headers, doc_id):
    response = session.post(
        f"{BASE}/api/v1/datasets/{MAIN_DATASET_ID}/documents/parse",
        headers=headers,
        json={"document_ids": [doc_id]},
        timeout=30,
    )
    response.raise_for_status()
    ensure_ok(response.json(), "parse cross fact card")


def wait_until_done(session, headers, doc_id):
    for _ in range(90):
        docs = list_documents(session, headers)
        doc = next((item for item in docs if item.get("id") == doc_id), None)
        if not doc:
            raise RuntimeError(f"Uploaded document disappeared: {doc_id}")
        run = str(doc.get("run", ""))
        chunk_count = doc.get("chunk_count") or doc.get("chunk_num") or 0
        if run in {"DONE", "3"} and int(chunk_count) > 0:
            return doc
        if run in {"FAIL", "4"}:
            raise RuntimeError(f"Parse failed: {doc}")
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for parse: {doc_id}")


def main() -> None:
    session, headers = login()
    old_docs = find_cross_fact_docs(session, headers)
    delete_documents(session, headers, [doc["id"] for doc in old_docs])
    doc_id = upload_document(session, headers)
    parse_document(session, headers, doc_id)
    parsed = wait_until_done(session, headers, doc_id)
    agent_id = create_or_update_agent(session, headers)
    print(
        {
            "agent_id": agent_id,
            "old_doc_ids": [doc["id"] for doc in old_docs],
            "new_doc_id": doc_id,
            "run": parsed.get("run"),
            "chunk_count": parsed.get("chunk_count") or parsed.get("chunk_num"),
        }
    )


if __name__ == "__main__":
    main()
