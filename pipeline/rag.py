import json
import chromadb
from chromadb.utils import embedding_functions


def build_or_load_store():
    client = chromadb.PersistentClient(path="chroma_store")
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name="fraud_patterns", embedding_function=embedding_fn
    )

    if collection.count() == 0:
        with open("data/fraud_patterns.json") as f:
            patterns = json.load(f)
        collection.add(
            ids=[p["id"] for p in patterns],
            documents=[p["text"] for p in patterns],
        )
        print(f"Embedded {len(patterns)} fraud patterns")

    return collection


def get_matching_patterns(vendor_name: str, detail: str, n_results: int = 3):
    collection = build_or_load_store()
    query = f"{vendor_name}: {detail}"
    results = collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0]
