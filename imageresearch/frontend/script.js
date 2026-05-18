const form = document.getElementById("researchForm");
const submitBtn = document.getElementById("submitBtn");
const progressWrap = document.getElementById("progressWrap");
const progressBar = document.getElementById("progressBar");
const statusText = document.getElementById("statusText");
const result = document.getElementById("result");

const statuses = [
  "Creating search plan...",
  "Searching image sources...",
  "Scoring candidates...",
  "Saving best image...",
];

let timer = null;
let statusIndex = 0;
let progress = 0;

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
  progressBar.style.background = "#b42318";
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
  if (!data.success || !data.selected_image) {
    result.innerHTML = `
      <h2>No image selected</h2>
      <p>${escapeHtml((data.warnings || ["No result found."])[0])}</p>
      ${renderWarnings(data.warnings)}
    `;
    return;
  }
  const image = data.selected_image;
  result.innerHTML = `
    <img src="${escapeHtml(image.public_url)}" alt="Selected image" />
    <div class="meta">
      <div><strong>Source</strong>${escapeHtml(image.source)}</div>
      <div><strong>Author</strong>${escapeHtml(image.author || "Unknown")}</div>
      <div><strong>License</strong>${escapeHtml(image.license_name)}</div>
      <div><strong>Final score</strong>${escapeHtml(image.final_score)}</div>
      <div><strong>Dimensions</strong>${escapeHtml(image.width || "?")} x ${escapeHtml(image.height || "?")}</div>
      <div><strong>Source link</strong><a href="${escapeHtml(image.source_url)}" target="_blank" rel="noreferrer">Open source page</a></div>
    </div>
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
    max_candidates: Number(document.getElementById("maxCandidates").value || 12),
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
