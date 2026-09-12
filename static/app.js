let currentSession = null;
let sessionItems = [];

const sessionsElement = document.getElementById("sessions");
const chatElement = document.getElementById("chat");
const titleElement = document.getElementById("title");
const statusElement = document.getElementById("status");
const errorElement = document.getElementById("error");
const inputElement = document.getElementById("message");
const sendButton = document.getElementById("send");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function showError(error) {
  errorElement.textContent = error.message;
  errorElement.hidden = false;
}

function clearError() {
  errorElement.textContent = "";
  errorElement.hidden = true;
}

function renderSessions() {
  sessionsElement.replaceChildren();
  for (const item of sessionItems) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `session${currentSession && item.session_id === currentSession.session_id ? " active" : ""}`;

    const name = document.createElement("strong");
    name.textContent = item.title;
    const count = document.createElement("small");
    count.textContent = `${item.message_count} messages`;
    button.append(name, count);
    button.addEventListener("click", () => selectSession(item.session_id));
    sessionsElement.appendChild(button);
  }
}

function renderMessage(message) {
  const row = document.createElement("article");
  row.className = `message ${message.role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = message.role === "user" ? "YOU" : "AI";

  const body = document.createElement("div");
  body.className = "message-body";
  const role = document.createElement("div");
  role.className = "message-role";
  role.textContent = message.role === "user" ? "You" : "Data Agent";
  const content = document.createElement("div");
  content.className = "message-content";
  content.textContent = message.content;
  body.append(role, content);
  row.append(avatar, body);
  return row;
}

function renderSession(session) {
  currentSession = session;
  titleElement.textContent = session.title;
  chatElement.replaceChildren();

  if (!session.messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.innerHTML = "<div><h2>Ask your data a question.</h2><div>Explore your database or run an ETL task.</div></div>";
    chatElement.appendChild(empty);
  } else {
    session.messages.forEach((message) => chatElement.appendChild(renderMessage(message)));
    window.scrollTo(0, document.body.scrollHeight);
  }
  renderSessions();
}

async function refreshSessions() {
  sessionItems = await api("/api/sessions");
  renderSessions();
}

async function selectSession(sessionId) {
  clearError();
  renderSession(await api(`/api/sessions/${sessionId}`));
}

async function createSession() {
  clearError();
  renderSession(await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title: "New session" }),
  }));
  await refreshSessions();
}

document.getElementById("new-session").addEventListener("click", createSession);

document.getElementById("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputElement.value.trim();
  if (!message || !currentSession) return;

  clearError();
  inputElement.value = "";
  sendButton.disabled = true;
  statusElement.textContent = "Working...";
  try {
    const result = await api(`/api/sessions/${currentSession.session_id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    renderSession(result.session);
    await refreshSessions();
  } catch (error) {
    showError(error);
  } finally {
    statusElement.textContent = "Ready";
    sendButton.disabled = false;
    inputElement.focus();
  }
});

inputElement.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.getElementById("form").requestSubmit();
  }
});

(async function initialize() {
  try {
    await refreshSessions();
    if (sessionItems.length) await selectSession(sessionItems[0].session_id);
    else await createSession();
  } catch (error) {
    showError(error);
  }
})();
