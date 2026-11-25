import asyncio

from src.chat.session_manager import get_session, update_session
from src.rag.answer_retrieval import create_rag_chain, format_docs
from src.rag.vector_store import create_vector_store

# Initialize RAG components once
retriever = create_vector_store()
rag_chain = create_rag_chain()


async def chat_with_history(session_id: str, message: str):

    # 1. Retrieve session
    session = await asyncio.to_thread(get_session, session_id)

    if session is None:
        raise ValueError("Session not found. Create a session first.")

    history = session["history"]

    # 2. Retrieve relevant chunks only once
    retrieved_chunks = await retriever.ainvoke(message)

    # 3. Format retrieved chunks
    context = format_docs(retrieved_chunks)

    # 4. Generate answer using those same chunks
    answer = await rag_chain.ainvoke({"context": context, "question": message})

    # 5. Update conversation history
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})

    # 6. Save history
    await asyncio.to_thread(update_session, session_id, history)

    # 7. Format retrieved chunks for response
    chunks = [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source", "Unknown"),
            "page": doc.metadata.get("page_number", doc.metadata.get("page", 0) + 1),
        }
        for doc in retrieved_chunks
    ]

    return {
        "session_id": session_id,
        "answer": answer,
        "history": history,
        "retrieved_chunks": chunks,
    }
