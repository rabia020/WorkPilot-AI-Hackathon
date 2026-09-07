from rag.retrieve import retrieve_docs
from llm import generate_answer


def ask_rag(question: str, docs=None):

    # ---------------------------------------
    # Retrieve relevant document chunks
    # (skipped when the caller already has them)
    # ---------------------------------------
    if docs is None:
        docs = retrieve_docs(question, top_k=5)

    if not docs:
        return "I couldn't find any relevant information in the company knowledge base."

    # ---------------------------------------
    # Combine retrieved chunks into one context
    # ---------------------------------------
    context = "\n\n".join(docs)

    # ---------------------------------------
    # Debug (optional)
    # ---------------------------------------
    print("\n" + "=" * 80)
    print("RETRIEVED CONTEXT")
    print("=" * 80)
    print(context)
    print("=" * 80)

    # ---------------------------------------
    # Generate answer using Mistral
    # ---------------------------------------
    answer = generate_answer(
        question=question,
        context=context
    )

    return answer


# ---------------------------------------------------------
# Standalone Testing
# ---------------------------------------------------------

if __name__ == "__main__":

    while True:

        question = input("\nQuestion (type 'exit' to quit): ")

        if question.lower() == "exit":
            break

        print("\nGenerating answer...\n")

        answer = ask_rag(question)

        print("\nAnswer:\n")
        print(answer)