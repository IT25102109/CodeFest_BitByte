"""
Flask backend for the Ashen Era Archive Assistant UI.

Serves the frontend and exposes a streaming endpoint that runs the agent
loop and pushes each step (query, results, evaluation, final answer) to
the browser live via Server-Sent Events - so the demo shows the actual
reasoning happening, not a spinner.
"""
import os
import sys
import json

from flask import Flask, Response, request, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from loader import load_all_documents          # noqa: E402
from chunker import chunk_all                   # noqa: E402
from retriever import Retriever                 # noqa: E402
from agent import LLMClient, answer_question_stream  # noqa: E402

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

print("Loading and indexing corpus (this happens once at startup)...")
_docs = load_all_documents()
_chunks = chunk_all(_docs)
_retriever = Retriever(_chunks)
print(f"Indexed {len(_chunks)} chunks from {len(_docs)} documents.")


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


@app.route("/api/ask")
def ask():
    question = request.args.get("question", "").strip()
    if not question:
        return {"error": "question is required"}, 400

    def event_stream():
        llm = LLMClient()
        try:
            for event in answer_question_stream(question, _retriever, llm):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/health")
def health():
    return {"status": "ok", "chunks_indexed": len(_chunks), "documents": len(_docs)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5055))
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
