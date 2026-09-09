"""
Splits loaded documents into chunks suitable for retrieval.

Strategy: split on paragraph/section boundaries first (so a chunk never
cuts a fact in half mid-sentence), then merge small paragraphs together
up to a target size, and hard-split anything still too long.
"""
import re

TARGET_CHARS = 900     
MAX_CHARS = 1600       
MIN_CHARS = 120        


def split_paragraphs(text):
    text = text.replace("\r\n", "\n")
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_document(doc):
    """
    doc: {path, folder, filename, authority_tier, text}
    Returns list of chunk dicts: {..doc metadata.., chunk_id, chunk_text}
    """
    paragraphs = split_paragraphs(doc["text"])
    chunks = []
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer.strip():
            chunks.append(buffer.strip())
        buffer = ""

    for para in paragraphs:
        if len(para) > MAX_CHARS:
            flush()
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sub = ""
            for s in sentences:
                if len(sub) + len(s) > TARGET_CHARS and sub:
                    chunks.append(sub.strip())
                    sub = s
                else:
                    sub = f"{sub} {s}".strip()
            if sub.strip():
                chunks.append(sub.strip())
            continue

        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) > TARGET_CHARS and buffer:
            flush()
            buffer = para
        else:
            buffer = candidate

    flush()

    result = []
    for i, ctext in enumerate(chunks):
        result.append({
            "path": doc["path"],
            "folder": doc["folder"],
            "filename": doc["filename"],
            "authority_tier": doc["authority_tier"],
            "chunk_id": f"{doc['filename']}::{i}",
            "chunk_text": ctext,
        })
    return result


def chunk_all(docs):
    all_chunks = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))
    return all_chunks


if __name__ == "__main__":
    from loader import load_all_documents
    docs = load_all_documents()
    chunks = chunk_all(docs)
    print(f"{len(docs)} documents -> {len(chunks)} chunks")
    lengths = [len(c["chunk_text"]) for c in chunks]
    print(f"avg chunk len: {sum(lengths)/len(lengths):.0f} chars, max: {max(lengths)}")
    # sanity check: show chunks from the gloamreach gazetteer entry
    for c in chunks:
        if "gazetteer" in c["filename"] and "founded" in c["chunk_text"].lower() and "gloamreach" in c["chunk_text"].lower():
            print("\n--- sample chunk (gloamreach founding, from gazetteer) ---")
            print(c["chunk_id"])
            print(c["chunk_text"][:400])
            break
