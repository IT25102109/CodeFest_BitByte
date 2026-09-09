"""
Runs the agent over every question in sample_questions.json and prints a
summary. This is for YOUR OWN judgment during development (the true
answers aren't provided) - read each result and sanity-check it against
the corpus. Also logs full search history per question, which is useful
material for your report and demo.
"""
import json
import os
import time
from loader import load_all_documents
from chunker import chunk_all
from retriever import Retriever
from agent import LLMClient, answer_question

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_QUESTIONS_PATH = os.path.join(_PROJECT_ROOT, "data", "sample_questions.json")
OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "data", "batch_results.json")


def main():
    with open(SAMPLE_QUESTIONS_PATH) as f:
        questions = json.load(f)

    print("Loading and indexing corpus...")
    docs = load_all_documents()
    chunks = chunk_all(docs)
    retriever = Retriever(chunks)
    llm = LLMClient()
    print(f"Indexed {len(chunks)} chunks from {len(docs)} documents.\n")

    results = []
    for q in questions:
        print(f"\n{'='*70}\n[{q['qid']}] ({q['track']})\n{q['question']}\n{'='*70}")
        start = time.time()
        try:
            result = answer_question(q["question"], retriever, llm, verbose=True)
            result["qid"] = q["qid"]
            result["question"] = q["question"]
            result["track"] = q["track"]
            result["elapsed_sec"] = round(time.time() - start, 1)
        except Exception as e:
            result = {"qid": q["qid"], "question": q["question"], "track": q["track"],
                       "answer": f"ERROR: {e}", "iterations": 0, "history": []}
        results.append(result)
        print(f"\n>>> ANSWER: {result['answer']}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nSaved {len(results)} results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
