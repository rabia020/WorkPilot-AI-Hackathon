# agents/rag_agent.py
from rag.retrieve import retrieve_docs
from rag.rag_chat import ask_rag


def rag_agent(state):
    """
    Company-knowledge node.

    Retrieval alone is not an answer: this node used to return only
    docs/context and never set a report, so a document question sent
    through /chat came back empty. It now generates the answer from
    the chunks it retrieved, reusing ask_rag so the empty-retrieval
    case stays honest instead of inviting a hallucinated answer.
    """
    query = state["query"]
    print(f"[RAG Agent] Retrieving docs for: {query}")

    docs = retrieve_docs(query, top_k=5)
    context = "\n\n".join(docs) if docs else "No relevant documents found."

    print(f"[RAG Agent] Retrieved {len(docs)} chunks")

    answer = ask_rag(query, docs=docs)

    return {
        "docs":           docs,
        "context":        context,
        "report":         answer,
        "final_response": answer,
    }
