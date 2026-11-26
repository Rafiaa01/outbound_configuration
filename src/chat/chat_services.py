import asyncio
import logging

from src.chat.intent_classifier import classify_intent
from src.chat.session_manager import get_session, update_session
from src.rag.answer_retrieval import create_rag_chain, format_docs
from src.rag.vector_store import create_vector_store

logger = logging.getLogger(__name__)
# Initialize RAG components once
retriever = create_vector_store()
rag_chain = create_rag_chain()


async def chat_with_history(session_id: str, message: str):

    # 1. Retrieve session
    session = await asyncio.to_thread(get_session, session_id)

    if session is None:
        raise ValueError("Session not found. Create a session first.")

    history = session["history"]

    # 2. Classify user intent
    intent = await classify_intent(message)
    logger.info("[INTENT] Message: %s | Intent: %s", message, intent)
    # Initialize empty retrieved chunks
    retrieved_chunks = []

    # 3. Handle greetings directly
    if intent == "greeting":
        answer = "Hello! How may I assist you with employee policies?"

    # 4. Handle unrelated questions directly
    elif intent == "unrelated":
        answer = (
            "I can help you with employee policies. "
            "Please ask me something related to HR."
        )
    # Handle goodbye
    elif intent == "goodbye":
        answer = "Goodbye! If you have more questions, feel free to ask."

    # 5. Only policy questions go through RAG
    else:
        retrieved_chunks = await retriever.ainvoke(message)

        context = format_docs(retrieved_chunks)

        answer = await rag_chain.ainvoke({"context": context, "question": message})

    # 6. Update conversation history
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})

    await asyncio.to_thread(update_session, session_id, history)

    # 7. Format retrieved chunks
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
        "end_call": intent == "goodbye",
    }
