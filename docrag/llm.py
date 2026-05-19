from typing import List, Optional

from openai import OpenAI, OpenAIError

from .config import CHAT_MODEL, EMBEDDING_MODEL, OPENAI_API_KEY


class LLMError(RuntimeError):
    pass


def client() -> Optional[OpenAI]:
    if not OPENAI_API_KEY:
        return None
    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except TypeError as exc:
        raise LLMError(
            "The OpenAI client dependency versions are incompatible. "
            "Rebuild the app with the updated requirements, then restart."
        ) from exc


def embed_texts(texts: List[str]) -> List[List[float]]:
    openai_client = client()
    if not openai_client:
        return []
    try:
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except OpenAIError as exc:
        raise LLMError("OpenAI embedding request failed: {error}".format(error=str(exc))) from exc


def answer_with_context(question: str, sources: List[dict]) -> Optional[str]:
    openai_client = client()
    if not openai_client:
        return None

    context = "\n\n".join(
        "[{idx}] {filename}, pages {pages}\n{text}".format(
            idx=i + 1,
            filename=source["filename"],
            pages=source["pages"],
            text=source["text"],
        )
        for i, source in enumerate(sources)
    )

    try:
        response = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You answer questions about uploaded research papers. "
                        "Use only the supplied context. Cite sources with bracketed numbers. "
                        "If the context is insufficient, say what is missing."
                    ),
                },
                {
                    "role": "user",
                    "content": "Question: {question}\n\nContext:\n{context}".format(
                        question=question,
                        context=context,
                    ),
                },
            ],
        )
        return response.choices[0].message.content or ""
    except OpenAIError as exc:
        raise LLMError("OpenAI answer request failed: {error}".format(error=str(exc))) from exc
