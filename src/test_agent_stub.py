"""
Tests agent.py's LOOP LOGIC (not real reasoning quality) using a scripted
stub LLM, since this sandbox has no internet access to call OpenRouter.

The stub simulates a plausible first pass (broad query, gets misled by
ephemera/wiki, correctly says "not enough") then a refined pass (adds
"codex" to the query, finds the authoritative chunk, says "enough").
This proves the search -> evaluate -> refine -> search loop is wired
correctly end to end before you swap in a real LLM tonight.
"""
import json
from retriever import Retriever
from loader import load_all_documents
from chunker import chunk_all
import agent


class StubLLM:
    def __init__(self):
        self.call_count = 0

    def complete(self, prompt):
        self.call_count += 1
        if "propose the NEXT search query" in prompt:
            if "none yet" in prompt:
                return "Gloamreach founded year"
            else:
                return "Gloamreach founded codex gazetteer authoritative"
        else:  # evaluation prompt
            if "gazetteer" in prompt.lower() and "246 as" in prompt.lower():
                return json.dumps({
                    "enough_info": True,
                    "missing": "",
                    "answer": "246 AS",
                    "source_note": "Codex Vaeloria I Gazetteer explicitly states this overrides "
                                    "popular accounts (which wrongly claim 286 AS per an ephemera contract)."
                })
            else:
                return json.dumps({
                    "enough_info": False,
                    "missing": "Wiki says founding is contested; need the codex/annals authoritative entry",
                    "answer": "",
                    "source_note": ""
                })


if __name__ == "__main__":
    docs = load_all_documents()
    chunks = chunk_all(docs)
    retriever = Retriever(chunks)
    llm = StubLLM()

    result = agent.answer_question(
        "State the precise year in the Age of Shadows that marks the true founding of Gloamreach.",
        retriever, llm, max_iterations=5
    )

    print("\n=== FINAL RESULT ===")
    print("Answer:", result["answer"])
    print("Source note:", result["source_note"])
    print("Iterations used:", result["iterations"])
    print("LLM calls made:", llm.call_count)

    assert result["answer"] == "246 AS", "Loop did not converge on correct answer!"
    assert result["iterations"] == 2, "Should resolve in 2 iterations (broad, then refined)"
    print("\n✓ Loop mechanics verified: correctly rejected first-pass ambiguity and refined the search.")
