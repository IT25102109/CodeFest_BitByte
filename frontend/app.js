const askBtn = document.getElementById("askBtn");
const questionInput = document.getElementById("questionInput");
const tracePanel = document.getElementById("tracePanel");
const emptyState = document.getElementById("emptyState");
const answerPanel = document.getElementById("answerPanel");
const answerText = document.getElementById("answerText");
const answerSource = document.getElementById("answerSource");
const answerMeta = document.getElementById("answerMeta");
const corpusStats = document.getElementById("corpusStats");
const sampleQuestionsEl = document.getElementById("sampleQuestions");

const iterationTemplate = document.getElementById("iterationTemplate");
const resultChipTemplate = document.getElementById("resultChipTemplate");

const SAMPLE_QUESTIONS = [
  "State the precise year in the Age of Shadows that marks the true founding of Gloamreach.",
  "In which year was the 'Gauntlet of Sorrowfell' actually forged?",
];

function init() {
  fetch("/api/health")
    .then((r) => r.json())
    .then((data) => {
      corpusStats.innerHTML = `<span class="stat-line">${data.documents} documents indexed · ${data.chunks_indexed} passages</span>`;
    })
    .catch(() => {
      corpusStats.innerHTML = `<span class="stat-line">corpus status unavailable</span>`;
    });

  SAMPLE_QUESTIONS.forEach((q) => {
    const chip = document.createElement("button");
    chip.className = "sample-chip";
    chip.type = "button";
    chip.textContent = q.length > 46 ? q.slice(0, 46) + "…" : q;
    chip.title = q;
    chip.addEventListener("click", () => {
      questionInput.value = q;
      runInquiry();
    });
    sampleQuestionsEl.appendChild(chip);
  });

  askBtn.addEventListener("click", runInquiry);
  questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) runInquiry();
  });
}

function folderClass(folder) {
  return ["codex", "chronicles", "wiki", "ephemera"].includes(folder) ? folder : "";
}

function runInquiry() {
  const question = questionInput.value.trim();
  if (!question) return;

  askBtn.disabled = true;
  askBtn.textContent = "Investigating…";
  emptyState.style.display = "none";
  answerPanel.classList.add("hidden");
  tracePanel.querySelectorAll(".iteration-card").forEach((el) => el.remove());

  const cardsByIteration = {};

  const source = new EventSource(`/api/ask?question=${encodeURIComponent(question)}`);

  source.onmessage = (e) => {
    const event = JSON.parse(e.data);

    if (event.type === "query") {
      const card = iterationTemplate.content.cloneNode(true).querySelector(".iteration-card");
      card.classList.add("pending");
      card.querySelector(".iteration-tag").textContent = `iteration ${event.iteration}`;
      card.querySelector(".query-text").textContent = event.query;
      tracePanel.appendChild(card);
      cardsByIteration[event.iteration] = card;
    }

    if (event.type === "results") {
      const card = cardsByIteration[event.iteration];
      const list = card.querySelector(".results-list");
      event.results.forEach((r) => {
        const chip = resultChipTemplate.content.cloneNode(true).querySelector(".result-chip");
        const folderEl = chip.querySelector(".chip-folder");
        folderEl.textContent = r.folder;
        folderEl.classList.add(folderClass(r.folder));
        chip.querySelector(".chip-filename").textContent = r.filename;
        chip.querySelector(".chip-snippet").textContent = r.snippet;
        list.appendChild(chip);
      });
      if (event.results.length === 0) {
        const none = document.createElement("p");
        none.className = "verdict";
        none.textContent = "No new passages found for this query.";
        list.appendChild(none);
      }
    }

    if (event.type === "evaluation") {
      const card = cardsByIteration[event.iteration];
      card.classList.remove("pending");
      const verdict = card.querySelector(".verdict");
      const status = card.querySelector(".iteration-status");
      if (event.enough_info) {
        card.classList.add("resolved");
        status.textContent = "resolved";
        status.classList.add("done");
        verdict.classList.add("resolved");
        verdict.textContent = "Sufficient, corroborated evidence found.";
      } else {
        card.classList.add("unresolved");
        status.textContent = "insufficient";
        verdict.classList.add("unresolved");
        verdict.textContent = event.missing || "Not enough to answer yet — refining search.";
      }
    }

    if (event.type === "final") {
      source.close();
      answerText.textContent = event.answer;
      answerSource.textContent = event.source_note || "";
      answerMeta.textContent = `resolved in ${event.iterations} iteration${event.iterations === 1 ? "" : "s"}`;
      answerPanel.classList.remove("hidden");
      answerPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
      askBtn.disabled = false;
      askBtn.textContent = "Investigate";
    }

    if (event.type === "error") {
      source.close();
      const errCard = document.createElement("div");
      errCard.className = "iteration-card unresolved";
      errCard.innerHTML = `<p class="verdict unresolved">Error: ${event.message}</p>`;
      tracePanel.appendChild(errCard);
      askBtn.disabled = false;
      askBtn.textContent = "Investigate";
    }
  };

  source.onerror = () => {
    source.close();
    askBtn.disabled = false;
    askBtn.textContent = "Investigate";
  };
}

init();
