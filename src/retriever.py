"""
Retrieval layer. Uses BM25 (lexical) so it works fully offline in dev/test.

SWAP-IN POINT FOR SUBMISSION: replace this with Voyage AI embeddings
(voyage-4-lite for queries, voyage-4-large for the corpus, per the
challenge appendix) + cosine similarity, or chromadb. Keep the same
`search(query, k)` interface so nothing else in the pipeline changes.
"""
import re
from rank_bm25 import BM25Okapi


def tokenize(text):
    return re.findall(r"[a-z0-9']+", text.lower())


class Retriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.tokenized = [tokenize(c["chunk_text"]) for c in chunks]
        self.bm25 = BM25Okapi(self.tokenized)

    def search(self, query, k=5, exclude_ids=None, folders=None):
        exclude_ids = exclude_ids or set()
        folders = set(folders) if folders else None
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(
            range(len(self.chunks)), key=lambda i: scores[i], reverse=True
        )
        results = []
        for i in ranked:
            chunk = self.chunks[i]
            if chunk["chunk_id"] in exclude_ids:
                continue
            if folders and chunk["folder"] not in folders:
                continue
            if scores[i] <= 0:
                break
            results.append({**chunk, "score": float(scores[i])})
            if len(results) >= k:
                break
        return results


if __name__ == "__main__":
    from loader import load_all_documents
    from chunker import chunk_all

    docs = load_all_documents()
    chunks = chunk_all(docs)
    retriever = Retriever(chunks)

    query = "Gloamreach founded year"
    print(f"Query: {query!r}\n")
    for r in retriever.search(query, k=5):
        print(f"[{r['folder']}/{r['filename']}] score={r['score']:.2f}")
        print(r["chunk_text"][:200].replace("\n", " "))
        print()
