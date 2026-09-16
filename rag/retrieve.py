import streamlit as st
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, CHROMA_PATH, RAG_COLLECTION, DEMO_MODE


# ==========================================================
# EMBEDDING MODEL
# ==========================================================

@st.cache_resource
def load_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL)


# ==========================================================
# CHROMA COLLECTION
# ==========================================================

@st.cache_resource
def get_chroma_collection():
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(RAG_COLLECTION)


# ==========================================================
# DEMO STORAGE
# ==========================================================

def _get_demo_documents():

    chunks = st.session_state.get(
        "demo_rag_chunks",
        []
    )

    embeddings = st.session_state.get(
        "demo_rag_embeddings",
        []
    )

    return chunks, embeddings


# ==========================================================
# DOCUMENT RETRIEVAL
# ==========================================================

def retrieve_docs(query: str, top_k: int = 3):

    model = load_embedding_model()

    # ======================================================
    # DEMO MODE
    # ======================================================

    if DEMO_MODE:

        chunks, embeddings = _get_demo_documents()

        if not chunks or not embeddings:
            return []

        query_embedding = model.encode(
            query,
            normalize_embeddings=True
        )

        # Calculate cosine similarity.
        # Embeddings are normalized, so dot product
        # is equivalent to cosine similarity.
        scores = []

        for i, embedding in enumerate(embeddings):

            score = sum(
                a * b
                for a, b in zip(
                    query_embedding,
                    embedding
                )
            )

            scores.append(
                (score, i)
            )

        scores.sort(
            key=lambda x: x[0],
            reverse=True
        )

        selected = scores[:top_k]

        return [
            chunks[i]
            for score, i in selected
        ]


    # ======================================================
    # ORIGINAL CHROMADB MODE
    # ======================================================

    collection = get_chroma_collection()

    query_embedding = model.encode(
        query,
        normalize_embeddings=True
    ).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    if (
        results.get("documents")
        and len(results["documents"]) > 0
    ):
        return results["documents"][0]

    return []


# ==========================================================
# STANDALONE TESTING
# ==========================================================

if __name__ == "__main__":

    query = input("Question: ")

    docs = retrieve_docs(query)

    print("\nRetrieved Documents:\n")

    for i, doc in enumerate(
        docs,
        start=1
    ):

        print("=" * 60)
        print(f"Chunk {i}")
        print("=" * 60)
        print(doc)