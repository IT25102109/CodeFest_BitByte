"""
Loads every document in the Ashen Era Archive into a uniform structure,
tagging each with its folder (source type) so we can later weight
authority (codex/annals > wiki > ephemera) during retrieval and evaluation.
"""
import os
import docx
import pdfplumber


_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_ROOT = os.environ.get(
    "ARCHIVE_ROOT",
    os.path.join(_SRC_DIR, "..", "data", "Ashen_Era_Archive")
)


AUTHORITY_TIER = {
    "codex": 1,
    "chronicles": 2,
    "wiki": 3,
    "ephemera": 4,
    "images": 5,
}


def read_txt(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def read_md(path):
    return read_txt(path)


def read_docx(path):
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs if p.text.strip())


def read_pdf(path):
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


READERS = {
    ".txt": read_txt,
    ".md": read_md,
    ".docx": read_docx,
    ".pdf": read_pdf,
}


def load_all_documents(root=ARCHIVE_ROOT, skip_folders=("images",)):
    """
    Returns a list of dicts: {path, folder, filename, authority_tier, text}
    Skips binary image files by default (handled separately for 1A).
    Prefers .docx over .pdf when both exist for the same base filename,
    since docx extraction is cleaner and we don't need duplicate content.
    """
    docs = []
    seen_basenames = set()

    for dirpath, _, filenames in os.walk(root):
        folder = os.path.relpath(dirpath, root).split(os.sep)[0]
        if folder in skip_folders:
            continue

       
        for fname in sorted(filenames, key=lambda f: (os.path.splitext(f)[1] != ".docx")):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in READERS:
                continue

            base = os.path.splitext(fname)[0]
            key = (folder, base)
            if key in seen_basenames:
                continue  

            full_path = os.path.join(dirpath, fname)
            try:
                text = READERS[ext](full_path)
            except Exception as e:
                print(f"WARN: failed to read {full_path}: {e}")
                continue

            if not text.strip():
                continue

            seen_basenames.add(key)
            docs.append({
                "path": full_path,
                "folder": folder,
                "filename": fname,
                "authority_tier": AUTHORITY_TIER.get(folder, 9),
                "text": text,
            })

    return docs


if __name__ == "__main__":
    docs = load_all_documents()
    print(f"Loaded {len(docs)} documents")
    by_folder = {}
    for d in docs:
        by_folder.setdefault(d["folder"], 0)
        by_folder[d["folder"]] += 1
    for folder, count in sorted(by_folder.items()):
        print(f"  {folder}: {count}")
