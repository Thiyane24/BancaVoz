let token = "";
const $ = (id) => document.getElementById(id);
const money = (minor) => `MZN ${(Number(minor || 0) / 100).toFixed(2)}`;
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) } });
  if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
  return response.json();
}
function setStatus(id, message) { $(id).textContent = message; }
async function loadDashboard() {
  setStatus("global-status", "Refreshing the ledger…");
  try {
    const [summary, stock, credits, entries] = await Promise.all([api("/summary"), api("/stock"), api("/credits"), api("/entries")]);
    $("net-value").textContent = money(summary.net_minor);
    $("sales-value").textContent = money(summary.sales_minor);
    $("expenses-value").textContent = money(summary.expenses_minor);
    $("net-label").textContent = "Verified ledger total";
    $("digest").textContent = summary.digest || "No digest is available yet.";
    $("digest").classList.remove("empty-state");
    renderStock(stock);
    renderCredits(credits);
    renderEntries(entries);
    setStatus("global-status", "");
  } catch (error) {
    setStatus("global-status", `Could not refresh: ${error.message}. Check the token or try again.`);
  }
  function renderCredits(items) {
    const target = $("credit-list");
    const rows = Object.entries(items).filter(([, value]) => Number(value) > 0);
    target.textContent = rows.length ? rows.map(([name, value]) => `${name}: ${money(value)}`).join("\n") : "No customers owe money.";
  }
  function renderEntries(items) {
    const target = $("entries-list");
    target.textContent = items.length ? items.slice(0, 10).map((item) => `${item.entry_type}: ${money(item.amount_minor)}`).join("\n") : "No entries yet.";
  }
}
function renderStock(items) {
  const target = $("stock-list");
  if (!items.length) { target.textContent = "No stock recorded yet."; return; }
  target.classList.remove("empty-state");
  target.innerHTML = items.map((item) => `<div><strong>${item.product}</strong> · ${item.quantity ?? "not counted"} available</div>`).join("");
}
$("signin-form").addEventListener("submit", async (event) => {
  event.preventDefault(); token = $("token").value.trim();
  setStatus("signin-status", "Checking access…");
  try { await api("/summary"); $("signin").hidden = true; $("dashboard").hidden = false; await loadDashboard(); }
  catch (error) { token = ""; setStatus("signin-status", `Sign in failed: ${error.message}`); }
});
$("signout").addEventListener("click", () => { token = ""; $("dashboard").hidden = true; $("signin").hidden = false; $("token").value = ""; });
document.querySelectorAll("[data-refresh]").forEach((button) => button.addEventListener("click", loadDashboard));
$("command-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const command = $("command").value.trim();
  if (!command) return;
  setStatus("command-status", "Sending command…");
  try {
    const response = await api("/command", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ utterance: command }) });
    setStatus("command-status", response.speech || "Command recorded.");
    await loadDashboard();
  } catch (error) { setStatus("command-status", `Command failed: ${error.message}`); }
});
$("mic").addEventListener("click", () => {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) { setStatus("command-status", "Speech recognition is not supported here. Type a command instead."); return; }
  const recognition = new Recognition(); recognition.onresult = (event) => { $("command").value = event.results[0][0].transcript; }; recognition.start();
});
