const form = document.getElementById("sim-form");
const input = document.getElementById("utterance");
const status = document.getElementById("sim-status");
const result = document.getElementById("sim-result");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const utterance = input.value.trim();
  if (!utterance) { status.textContent = "Say or type a command first."; return; }
  status.textContent = "Listening to the ledger…"; result.hidden = true;
  try {
    const response = await fetch("/sim/utterance", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ utterance }) });
    if (!response.ok) throw new Error("The simulator could not respond.");
    const data = await response.json();
    document.getElementById("speech").textContent = data.speech || "No response.";
    document.getElementById("tool-calls").textContent = JSON.stringify(data.tool_calls || [], null, 2);
    result.hidden = false; status.textContent = "";
  } catch (error) { status.textContent = error.message; }
});
document.getElementById("listen").addEventListener("click", () => {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) { status.textContent = "Speech recognition is not supported here. Type a command instead."; return; }
  const recognition = new Recognition();
  recognition.onstart = () => { status.textContent = "Listening…"; };
  recognition.onresult = (event) => { input.value = event.results[0][0].transcript; form.requestSubmit(); };
  recognition.onerror = () => { status.textContent = "Microphone input was unavailable. You can type instead."; };
  recognition.start();
});
