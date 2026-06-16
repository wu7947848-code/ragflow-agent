import time
from pathlib import Path

from create_ragflow_agent import BASE, FACT_DATASET_ID, MAIN_DATASET_ID, create_or_update_agent, login


FACT_CARD = Path(r"C:\Users\wangl\School\ragflow_ready_payload_v3\99_fact_cards.md")
TARGET_DATASETS = [MAIN_DATASET_ID, FACT_DATASET_ID]


def ensure_ok(payload: dict, action: str) -> None:
    if payload.get("code") not in (0, None):
        raise RuntimeError(f"{action} failed: {payload}")


def list_documents(session, headers, dataset_id):
    response = session.get(
        f"{BASE}/api/v1/datasets/{dataset_id}/documents",
        headers=headers,
        params={"page": 1, "page_size": 200},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    ensure_ok(payload, "list documents")
    data = payload.get("data", {})
    if isinstance(data, list):
        return data
    return data.get("docs") or data.get("documents") or []


def delete_documents(session, headers, dataset_id, doc_ids):
    if not doc_ids:
        return
    response = session.delete(
        f"{BASE}/api/v1/datasets/{dataset_id}/documents",
        headers=headers,
        json={"ids": doc_ids},
        timeout=30,
    )
    response.raise_for_status()
    ensure_ok(response.json(), f"delete old fact cards in {dataset_id}")


def upload_document(session, headers, dataset_id):
    with FACT_CARD.open("rb") as file_obj:
        response = session.post(
            f"{BASE}/api/v1/datasets/{dataset_id}/documents",
            headers={"Authorization": headers["Authorization"]},
            files={"file": (FACT_CARD.name, file_obj, "text/markdown")},
            timeout=60,
        )
    response.raise_for_status()
    payload = response.json()
    ensure_ok(payload, f"upload fact cards to {dataset_id}")
    data = payload.get("data", [])
    docs = data if isinstance(data, list) else [data]
    return docs[0]["id"]


def parse_document(session, headers, dataset_id, doc_id):
    response = session.post(
        f"{BASE}/api/v1/datasets/{dataset_id}/documents/parse",
        headers=headers,
        json={"document_ids": [doc_id]},
        timeout=30,
    )
    response.raise_for_status()
    ensure_ok(response.json(), f"parse fact cards in {dataset_id}")


def wait_until_done(session, headers, dataset_id, doc_id):
    for _ in range(90):
        doc = next((item for item in list_documents(session, headers, dataset_id) if item.get("id") == doc_id), None)
        if not doc:
            raise RuntimeError(f"Uploaded document disappeared: {doc_id}")
        run = str(doc.get("run", ""))
        chunk_count = int(doc.get("chunk_count") or doc.get("chunk_num") or 0)
        if run in {"DONE", "3"} and chunk_count > 0:
            return doc
        if run in {"FAIL", "4"}:
            raise RuntimeError(f"Parse failed: {doc}")
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for parse: {doc_id}")


def update_dataset(session, headers, dataset_id):
    old_docs = [
        doc
        for doc in list_documents(session, headers, dataset_id)
        if str(doc.get("name", "")).startswith("99_fact_cards")
    ]
    delete_documents(session, headers, dataset_id, [doc["id"] for doc in old_docs])
    doc_id = upload_document(session, headers, dataset_id)
    parse_document(session, headers, dataset_id, doc_id)
    parsed = wait_until_done(session, headers, dataset_id, doc_id)
    return {
        "dataset_id": dataset_id,
        "old_doc_ids": [doc["id"] for doc in old_docs],
        "new_doc_id": doc_id,
        "run": parsed.get("run"),
        "chunk_count": parsed.get("chunk_count") or parsed.get("chunk_num"),
    }


def main() -> None:
    session, headers = login()
    results = [update_dataset(session, headers, dataset_id) for dataset_id in TARGET_DATASETS]
    agent_id = create_or_update_agent(session, headers)
    print({"agent_id": agent_id, "results": results})


if __name__ == "__main__":
    main()
