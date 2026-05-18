const form = document.getElementById("researchForm");
const submitBtn = document.getElementById("submitBtn");
const progressWrap = document.getElementById("progressWrap");
const progressBar = document.getElementById("progressBar");
const statusText = document.getElementById("statusText");
const result = document.getElementById("result");
const maxCandidates = document.getElementById("maxCandidates");
const candidateValue = document.getElementById("candidateValue");

const statuses = [
  "Creating search plan...",
  "Searching image sources...",
  "Scoring candidates...",
  "Saving best images...",
];

let timer = null;
let statusIndex = 0;
let progress = 0;

function syncCandidateValue() {
  candidateValue.textContent = maxCandidates.value;
}

function startProgress() {
  clearInterval(timer);
  progress = 0;
  statusIndex = 0;
  progressWrap.classList.remove("hidden");
  progressBar.style.background = "";
  progressBar.style.width = "0%";
  statusText.classList.remove("error");
  statusText.textContent = statuses[0];
  timer = setInterval(() => {
    progress = Math.min(88, progress + Math.max(1, (90 - progress) * 0.06));
    statusIndex = Math.min(statuses.length - 1, Math.floor(progress / 24));
    progressBar.style.width = `${progress}%`;
    statusText.textContent = statuses[statusIndex];
  }, 450);
}

function finishProgress() {
  clearInterval(timer);
  progressBar.style.width = "100%";
  statusText.textContent = "Done";
}

function failProgress(message) {
  clearInterval(timer);
  progressBar.style.background = "#ff5d6c";
  statusText.classList.add("error");
  statusText.textContent = message;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function renderWarnings(warnings) {
  if (!warnings || !warnings.length) return "";
  return `<div class="warnings"><strong>Warnings</strong><br>${warnings.map(escapeHtml).join("<br>")}</div>`;
}

function renderResult(data) {
  result.classList.remove("hidden");
  const images = data.selected_images?.length ? data.selected_images : (data.selected_image ? [data.selected_image] : []);
  if (!data.success || !images.length) {
    result.innerHTML = `
      <h2>No image selected</h2>
      <p>${escapeHtml((data.warnings || ["No result found."])[0])}</p>
      ${renderWarnings(data.warnings)}
    `;
    return;
  }
  const cards = images.map((image, index) => `
    <article class="image-card">
      <img src="${escapeHtml(image.public_url)}" alt="Selected image ${index + 1}" />
      <div class="image-info">
        <b>#${index + 1} - ${escapeHtml(image.source)}</b>
        <span>${escapeHtml(image.author || "Unknown author")}</span>
        <span>${escapeHtml(image.license_name)} - score ${escapeHtml(image.final_score)}</span>
        <a href="${escapeHtml(image.source_url)}" target="_blank" rel="noreferrer">Source</a>
      </div>
    </article>
  `).join("");
  result.innerHTML = `
    <div class="result-head">
      <h2>Selected images</h2>
      <p>${images.length} saved - ${escapeHtml(data.candidate_count)} scored</p>
    </div>
    <div class="gallery">${cards}</div>
    ${renderWarnings(data.warnings)}
  `;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  result.classList.add("hidden");
  submitBtn.disabled = true;
  startProgress();

  const payload = {
    prompt: document.getElementById("prompt").value.trim(),
    style: document.getElementById("style").value.trim() || null,
    preferred_orientation: document.getElementById("orientation").value,
    image_type: document.getElementById("imageType").value,
    max_candidates: Number(maxCandidates.value || 6),
  };

  try {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Request failed");
    finishProgress();
    renderResult(data);
  } catch (error) {
    failProgress(error.message || "Request failed");
  } finally {
    submitBtn.disabled = false;
  }
});

maxCandidates.addEventListener("input", syncCandidateValue);
syncCandidateValue();
