"""
The core 1C loop: search -> evaluate -> refine query -> search again,
until the model has enough (and enough CORROBORATED) information to answer.

Key design decision (from exploring the real corpus): a passage that
LOOKS confident is not necessarily correct. Ephemera documents (letters,
contracts, ballads) state "popular" facts in plain, confident prose with
no hedging at all, while the actual authoritative source (codex/annals)
explicitly flags itself as overriding "popular accounts." So the
evaluation step must actively check for corroboration across source
tiers, not just check "did I find A plausible answer."
"""
import os
import json
from dotenv import load_dotenv
from retriever import Retriever

load_dotenv()

MAX_ITERATIONS = 5

QUERY_GEN_PROMPT = """You are researching an answer to a question about a fantasy archive corpus.

Question: {question}

Search history so far (queries already tried, and what was found):
{history}

Based on what's still missing, propose the NEXT search query to run.
If this is the first search, propose a direct query for the question's key entity/fact.
If prior results were unhelpful, disputed, or contradicted, propose a MORE SPECIFIC query
(e.g. add "codex", "annals", "gazetteer", or the specific artifact/location name) to find
the authoritative source rather than repeating the same broad search.

Respond with ONLY the search query text, nothing else."""

EVAL_PROMPT = """You are evaluating whether you have enough reliable information to answer a question
about a fantasy archive corpus, where sources sometimes disagree.

Question: {question}

Retrieved passages so far:
{passages}

IMPORTANT: This corpus deliberately contains "popular" but INCORRECT claims in informal
sources (letters, contracts, ballads, sermons, field reports), while the CODEX and ANNALS
are the authoritative sources and often explicitly say things like "popular accounts wrongly
claim otherwise" or "the authoritative record states." A confident tone in a letter or ballad
is NOT a sign of correctness.

Decide:
1. Do you have an answer from an authoritative source (codex/annals), or an answer that is
   corroborated by multiple independent sources?
2. If you only have an answer from ephemera/wiki/chronicles with no codex confirmation, you
   do NOT have enough yet - you must search specifically for the codex/annals entry.
3. If sources conflict, prefer the codex/annals version and note the discrepancy.
4. A codex passage that explicitly corrects popular accounts is decisive even when
    wiki, chronicles, or ephemera passages say the date is unknown or give another year.

Respond in JSON only:
{{"enough_info": true/false, "missing": "what's still needed, or empty string if enough",
  "answer": "your answer if enough_info is true, else empty string",
  "source_note": "which document/tier the answer came from, and whether it was corroborated"}}"""

FINAL_SYNTHESIS_PROMPT = """Answer the question using only the retrieved archive passages below.

Question: {question}

Retrieved passages:
{passages}

Give the best evidence-based answer available. If the passages conflict or do not
establish the answer, say so plainly rather than inventing a fact. Mention the
most relevant source filename(s) and state that the answer was not fully
corroborated if no authoritative source is present.

Source priority is strict: codex entries are authoritative and override wiki,
chronicles, and ephemera. If a codex entry explicitly says popular accounts are
wrong and gives a date, answer with that codex date.

Return JSON only:
{{"answer": "...", "source_note": "..."}}"""


class LLMClient:
    """
    Thin wrapper around an OpenAI-compatible chat completion call.
    Point base_url at OpenRouter for the real submission:
        base_url="https://openrouter.ai/api/v1"
        api_key=os.environ["OPENROUTER_API_KEY"]
        model="meta-llama/llama-3.1-8b-instruct"
    """
    def __init__(self, base_url=None, api_key=None, model=None):
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = model or os.environ.get("LLM_MODEL", "meta-llama/llama-3.1-8b-instruct")

    def complete(self, prompt):
        from openai import OpenAI
        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()


def format_history(history):
    if not history:
        return "(none yet - this is the first search)"
    lines = []
    for h in history:
        lines.append(f"- Query: {h['query']!r} -> {len(h['results'])} results from: "
                      f"{', '.join(sorted(set(r['folder'] for r in h['results'])))}")
    return "\n".join(lines)


def format_passages(all_results):
    lines = []
    ordered_results = sorted(
        all_results,
        key=lambda r: (r.get("authority_tier", 99), r["filename"]),
    )
    for r in ordered_results:
        lines.append(f"[{r['folder']}/{r['filename']}] {r['chunk_text'][:1000]}")
    return "\n\n".join(lines)


def retrieve_with_authority(question, query, retriever, seen_ids):
    """Combine the normal search with a targeted codex lookup."""
    results = retriever.search(query, k=5, exclude_ids=seen_ids)
    authoritative = retriever.search(
        f"{question} codex authoritative record",
        k=3,
        exclude_ids=seen_ids | {r["chunk_id"] for r in results},
        folders={"codex"},
    )
    return results + authoritative


def answer_question_stream(question, retriever, llm, max_iterations=MAX_ITERATIONS):
    """Yield progress events for the browser while researching a question."""
    history = []
    all_results = []
    seen_ids = set()

    for iteration in range(1, max_iterations + 1):
        query = llm.complete(QUERY_GEN_PROMPT.format(
            question=question, history=format_history(history)
        ))
        yield {"type": "query", "iteration": iteration, "query": query}

        results = retrieve_with_authority(question, query, retriever, seen_ids)
        for result in results:
            seen_ids.add(result["chunk_id"])
        all_results.extend(results)
        history.append({"query": query, "results": results})
        yield {
            "type": "results",
            "iteration": iteration,
            "results": [
                {
                    "folder": result["folder"],
                    "filename": result["filename"],
                    "snippet": result["chunk_text"][:200],
                }
                for result in results
            ],
        }

        eval_raw = llm.complete(EVAL_PROMPT.format(
            question=question, passages=format_passages(all_results)
        ))
        try:
            eval_json = json.loads(eval_raw)
        except json.JSONDecodeError:
            eval_json = {
                "enough_info": False,
                "missing": eval_raw,
                "answer": "",
                "source_note": "",
            }

        yield {
            "type": "evaluation",
            "iteration": iteration,
            "enough_info": bool(eval_json.get("enough_info")),
            "missing": eval_json.get("missing", ""),
        }

        if eval_json.get("enough_info"):
            yield {
                "type": "final",
                "answer": eval_json.get("answer", ""),
                "source_note": eval_json.get("source_note", ""),
                "iterations": iteration,
            }
            return

    try:
        synthesis_raw = llm.complete(FINAL_SYNTHESIS_PROMPT.format(
            question=question, passages=format_passages(all_results)
        ))
        synthesis = json.loads(synthesis_raw)
        answer = synthesis.get("answer", "")
        source_note = synthesis.get("source_note", "")
    except (json.JSONDecodeError, AttributeError, TypeError):
        answer = "The available passages did not establish a fully corroborated answer."
        source_note = "Search budget exhausted without authoritative corroboration."

    yield {
        "type": "final",
        "answer": answer,
        "source_note": source_note,
        "iterations": max_iterations,
    }


def answer_question(question, retriever, llm, max_iterations=MAX_ITERATIONS, verbose=True):
    history = []
    all_results = []
    seen_ids = set()

    for i in range(max_iterations):
        # 1. Decide next search query
        query = llm.complete(QUERY_GEN_PROMPT.format(
            question=question, history=format_history(history)
        ))
        if verbose:
            print(f"\n[iteration {i+1}] search query: {query!r}")

        # 2. Retrieve
        results = retrieve_with_authority(question, query, retriever, seen_ids)
        for r in results:
            seen_ids.add(r["chunk_id"])
        all_results.extend(results)
        history.append({"query": query, "results": results})

        if verbose:
            for r in results:
                print(f"    -> [{r['folder']}/{r['filename']}] {r['chunk_text'][:100]!r}")

        # 3. Evaluate: enough info yet?
        eval_raw = llm.complete(EVAL_PROMPT.format(
            question=question, passages=format_passages(all_results)
        ))
        try:
            eval_json = json.loads(eval_raw)
        except json.JSONDecodeError:
            eval_json = {"enough_info": False, "missing": eval_raw, "answer": "", "source_note": ""}

        if verbose:
            print(f"    evaluation: {eval_json}")

        if eval_json.get("enough_info"):
            return {
                "answer": eval_json["answer"],
                "source_note": eval_json.get("source_note", ""),
                "iterations": i + 1,
                "history": history,
            }

    # Ran out of iterations - return best guess with a flag
    return {
        "answer": "(could not confidently resolve within iteration budget)",
        "source_note": "",
        "iterations": max_iterations,
        "history": history,
    }


if __name__ == "__main__":
    from loader import load_all_documents
    from chunker import chunk_all

    docs = load_all_documents()
    chunks = chunk_all(docs)
    retriever = Retriever(chunks)

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("No OPENROUTER_API_KEY set - skipping live run.")
        print("Set it and run: python3 agent.py")
    else:
        llm = LLMClient()
        result = answer_question(
            "State the precise year in the Age of Shadows that marks the true founding of Gloamreach.",
            retriever, llm
        )
        print("\n=== FINAL ===")
        print(result["answer"])
        print(result["source_note"])
