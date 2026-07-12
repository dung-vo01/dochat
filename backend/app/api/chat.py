import json
from flask import Blueprint, request, Response
from app.clients.openai import openai_client, CHAT_MODEL
from app.services.rag import retrieve, build_system_prompt

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("", methods=["POST"])
def chat():
    # Retrieves relevant chunks from ChromaDB based on the latest user message
    # Injects them into the system prompt as context
    # Streams the response

    data = request.get_json(force=True)
    messages = data.get("messages", [])

    if not messages:
        return {"error": "messages is required"}, 400

    # Get the latest user message to use as the search query
    latest_user_message = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    # Retrieve relevant chunks (empty list if nothing uploaded yet)
    context_chunks = retrieve(latest_user_message)
    system_prompt = build_system_prompt(context_chunks)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    def generate():
        stream = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=full_messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                # Server-Sent Events format: "data: <json>\n\n"
                payload = json.dumps({"text": delta})
                yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
