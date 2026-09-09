# Ashen Era Archive Assistant — Sub-track 1C

An iterative-search AI assistant for SLIIT Codefest 2026 (AI Competition, powered by IFS).
Answers multi-hop questions over the Ashen Era Archive by searching, evaluating what's
still missing, and refining its search — repeating until it has a corroborated answer.

## Project layout

```
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── loader.py          # reads all corpus formats (md, txt, docx, pdf)
│   ├── chunker.py         # splits documents into retrievable passages
│   ├── retriever.py       # BM25 lexical search (swap for embeddings if desired)
│   ├── agent.py           # the core iterative search/evaluate/refine loop
│   └── run_batch.py       # runs the agent over sample_questions.json
├── data/                  # put the Ashen_Era_Archive/ folder here (not committed)
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   └── limitations.md
├── ai_usage/
│   └── ai-usage-disclosure.md
└── configuration-example/
```

## Setup

1. **Python 3.10+** recommended. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get an OpenRouter API key** (free, no card required):
   - Sign up at https://openrouter.ai with email/Google/GitHub
   - Create an API key from account settings

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # edit .env and paste your OPENROUTER_API_KEY
   ```

5. **Place the corpus:** copy the `Ashen_Era_Archive/` folder into `data/` so you have
   `data/Ashen_Era_Archive/chronicles`, `/codex`, `/ephemera`, `/wiki`, `/images`.

## Running

Test the loader/chunker/retriever on their own:
```bash
cd src
python3 loader.py
python3 chunker.py
python3 retriever.py
```

Run the agent on a single question (edit the question in `agent.py`'s `__main__`, or
use `run_batch.py` for the full question set):
```bash
python3 agent.py
```

Run the full sample question set and see pass/fail against your own judgment:
```bash
python3 run_batch.py
```

## How it works

See `docs/architecture.md` for the full design. In short: the agent runs a loop of
(1) generate a search query, (2) retrieve passages via BM25, (3) evaluate whether it has
a *corroborated* answer yet — specifically checking whether the answer comes from an
authoritative source (codex/annals) or is contradicted by one — and (4) if not, refines
the query and searches again, up to 5 iterations.
