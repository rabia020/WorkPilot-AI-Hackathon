import streamlit as st
from sentence_transformers import SentenceTransformer
import chromadb

from config import EMBEDDING_MODEL, CHROMA_PATH, RAG_COLLECTION


@st.cache_resource
def load_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL)


@st.cache_resource
def get_chroma_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # get_collection would raise on a fresh database, breaking import
    # before anything could ingest documents.
    return client.get_or_create_collection(RAG_COLLECTION)


model = load_embedding_model()
collection = get_chroma_collection()


def retrieve_docs(query: str, top_k: int = 3):

    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    # Return only the retrieved document texts
    if results["documents"] and len(results["documents"]) > 0:
        return results["documents"][0]

    return []


if __name__ == "__main__":

    query = input("Question: ")

    docs = retrieve_docs(query)

    print("\nRetrieved Documents:\n")

    for i, doc in enumerate(docs, start=1):
        print("=" * 60)
        print(f"Chunk {i}")
        print("=" * 60)
        print(doc)