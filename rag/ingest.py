import os

import streamlit as st
from pypdf import PdfReader
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
# PDF LOADING
# ==========================================================

def load_pdf(file_path):
    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


# ==========================================================
# TEXT CHUNKING
# ==========================================================

def chunk_text(text, chunk_size=500, overlap=100):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


# ==========================================================
# DEMO STORAGE
# ==========================================================

def _init_demo_rag():

    if "demo_rag_documents" not in st.session_state:
        st.session_state["demo_rag_documents"] = []

    if "demo_rag_chunks" not in st.session_state:
        st.session_state["demo_rag_chunks"] = []

    if "demo_rag_embeddings" not in st.session_state:
        st.session_state["demo_rag_embeddings"] = []


def _store_demo_document(filename, chunks, embeddings):

    _init_demo_rag()

    st.session_state["demo_rag_documents"].append({
        "filename": filename,
        "chunks": len(chunks),
    })

    st.session_state["demo_rag_chunks"].extend(chunks)

    st.session_state["demo_rag_embeddings"].extend(
        embeddings
    )


# ==========================================================
# PDF INGESTION
# ==========================================================

def ingest_pdf(file_path):

    text = load_pdf(file_path)

    if not text.strip():
        return {
            "success": False,
            "message": "No readable text was found in the PDF."
        }

    chunks = chunk_text(text)

    if not chunks:
        return {
            "success": False,
            "message": "The PDF did not contain usable text."
        }

    model = load_embedding_model()

    # ======================================================
    # DEMO MODE
    # ======================================================

    if DEMO_MODE:

        embeddings = model.encode(
            chunks,
            normalize_embeddings=True
        ).tolist()

        filename = os.path.basename(file_path)

        _store_demo_document(
            filename,
            chunks,
            embeddings
        )

        return {
            "success": True,
            "message": (
                f"Successfully processed '{filename}' "
                f"into {len(chunks)} document chunks."
            ),
            "chunks": len(chunks),
        }

    # ======================================================
    # ORIGINAL CHROMADB MODE
    # ======================================================

    collection = get_chroma_collection()

    base = os.path.basename(file_path).replace(".pdf", "")

    embeddings = model.encode(
        chunks,
        normalize_embeddings=True
    ).tolist()

    ids = [
        f"{base}_{i}"
        for i in range(len(chunks))
    ]

    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=ids,
        metadatas=[
            {
                "source": os.path.basename(file_path),
                "chunk": i,
            }
            for i in range(len(chunks))
        ],
    )

    return {
        "success": True,
        "message": (
            f"Successfully processed '{os.path.basename(file_path)}' "
            f"into {len(chunks)} document chunks."
        ),
        "chunks": len(chunks),
    }