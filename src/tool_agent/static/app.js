const api = async (path, options = {}) => {
  const response = await fetch("/api" + path, Object.assign({
    headers: {"Content-Type": "application/json"}
  }, options));
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Operação não concluída.");
  return body;
};
const safe = value => String(value).replace(/[&<>"']/g, char =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[char]));
const toast = text => {
  const node = document.querySelector("#toast"); node.textContent = text;
  node.classList.add("show"); setTimeout(() => node.classList.remove("show"), 2500);
};
let active = {threadId:null, question:null};

function showView(id) {
  document.querySelectorAll(".view,nav button").forEach(node => node.classList.remove("active"));
  document.querySelector("#" + id).classList.add("active");
  document.querySelector('[data-view="' + id + '"]').classList.add("active");
  document.querySelector("#page-title").textContent =
    ({agent:"Agente",datasets:"Datasets",runs:"Execuções",graph:"Arquitetura"})[id];
}
document.querySelectorAll("nav button").forEach(button =>
  button.onclick = () => showView(button.dataset.view));
document.querySelectorAll(".examples button").forEach(button =>
  button.onclick = () => { document.querySelector("#question").value = button.textContent; });

function render(result) {
  active = {threadId:result.thread_id, question:result.question};
  document.querySelector("#thread-label").textContent = result.thread_id.slice(0, 12);
  document.querySelector("#metrics").textContent =
    (result.input_tokens + result.output_tokens) + " tokens · " + result.duration_ms + " ms";
  document.querySelector("#trace").innerHTML = result.traces.map((step, index) =>
    '<div class="trace-step"><span>' + (index + 1) + '</span><div><b>' +
    safe(step.node || "step") + "</b><p>" + safe(step.tool || step.detail || step.status) +
    "</p></div></div>"
  ).join("");
  document.querySelector("#answer").textContent = result.answer || "";
  const approval = document.querySelector("#approval");
  if (result.status === "approval_required") {
    approval.className = "approval";
    approval.innerHTML = '<b>Aprovação necessária</b><p>O agente quer acessar uma fonte governada.</p><div><button class="approve" onclick="resumeAgent(true)">Aprovar</button><button class="deny" onclick="resumeAgent(false)">Recusar</button></div>';
  } else { approval.className = ""; approval.innerHTML = ""; }
}

async function runAgent() {
  const question = document.querySelector("#question").value.trim();
  if (question.length < 3) return toast("Descreva um problema.");
  const button = document.querySelector("#run-agent"); button.disabled = true;
  button.textContent = "Executando grafo...";
  try {
    const result = await api("/agent/run", {method:"POST", body:JSON.stringify({
      question, live:document.querySelector("#live").checked
    })});
    render(result); loadRuns(); toast("Execução concluída.");
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; button.textContent = "Executar agente →"; }
}
window.resumeAgent = async approved => {
  try {
    const result = await api("/agent/" + active.threadId + "/resume", {
      method:"POST", body:JSON.stringify({question:active.question, approved})
    });
    render(result); loadRuns(); toast(approved ? "Execução aprovada." : "Execução recusada.");
  } catch (error) { toast(error.message); }
};

async function loadCapabilities() {
  const data = await api("/capabilities");
  document.querySelector("#runtime-label").textContent =
    data.live_available ? "Groq disponível" : "Simulation";
  document.querySelector("#model-label").textContent = data.model;
  document.querySelector("#live").disabled = !data.live_available;
}
async function loadDatasets() {
  const items = await api("/datasets");
  document.querySelector("#dataset-list").innerHTML = items.map(item =>
    '<article class="card"><span>DATASET #' + item.id + "</span><h3>" + safe(item.name) +
    "</h3><p>" + item.bytes + " bytes · " + item.created_at + "</p></article>"
  ).join("") || '<div class="empty">Nenhum CSV cadastrado.</div>';
}
async function loadRuns() {
  const items = await api("/runs");
  document.querySelector("#run-list").innerHTML = items.map(item =>
    '<div class="trow"><span>' + safe(item.status) + "</span><span>" + safe(item.question) +
    "</span><span>" + safe(item.mode) + "</span><span>" + item.duration_ms +
    " ms</span><span>" + (item.input_tokens + item.output_tokens) + "</span></div>"
  ).join("") || '<div class="empty">Nenhuma execução.</div>';
}
document.querySelector("#run-agent").onclick = runAgent;
document.querySelector("#refresh-runs").onclick = loadRuns;
const dialog = document.querySelector("#dataset-dialog");
document.querySelector("#open-dataset").onclick = () => dialog.showModal();
document.querySelectorAll(".close").forEach(button =>
  button.onclick = () => button.closest("dialog").close());
document.querySelector("#dataset-form").onsubmit = async event => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.target));
  try {
    const result = await api("/datasets", {method:"POST", body:JSON.stringify(payload)});
    event.target.reset(); dialog.close(); await loadDatasets();
    document.querySelector("#question").value = "Analise o dataset #" + result.id;
    toast("Dataset cadastrado.");
  } catch (error) { toast(error.message); }
};
loadCapabilities().catch(() => {}); loadDatasets().catch(() => {}); loadRuns().catch(() => {});

