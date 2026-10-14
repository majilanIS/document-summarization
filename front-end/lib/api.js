// Requests go to /api/* on this Next.js server, which forwards them to the
// FastAPI back-end (see app/api/[...path]/route.js). Set NEXT_PUBLIC_API_URL
// only to call a back-end directly instead.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

async function request(path, options) {
  let response;

  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new Error(
      "Can't reach the server. Check that the front-end is still running."
    );
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        // FastAPI validation errors: [{ msg, loc, ... }]
        message = body.detail.map((d) => d.msg).join(". ");
      }
    } catch {
      // Not JSON; keep the generic message.
    }

    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}

function postJson(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function checkHealth() {
  return request("/api/health");
}

export function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/api/documents/upload", { method: "POST", body: form });
}

export function generateSummary(documentId, length) {
  return postJson("/api/summaries/generate", {
    document_id: documentId,
    length,
  });
}

export function getDocument(documentId) {
  return request(`/api/documents/${encodeURIComponent(documentId)}`);
}

export function listDocuments() {
  return request("/api/documents");
}

export function deleteDocument(documentId) {
  return request(`/api/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
}

export function sendFeedback({ summaryId, rating, aspects }) {
  return postJson("/api/feedback", {
    summary_id: summaryId,
    rating,
    aspects,
  });
}

export function listFeedback() {
  return request("/api/feedback");
}

export function getFeedbackStats() {
  return request("/api/feedback/stats");
}

export function getRewardModel() {
  return request("/api/feedback/reward-model");
}

export function getChat(documentId) {
  return request(`/api/chat/${encodeURIComponent(documentId)}`);
}

/** Resolves to { question, answer }, both saved messages. */
export function sendChatMessage(documentId, message) {
  return postJson(`/api/chat/${encodeURIComponent(documentId)}`, { message });
}

export function clearChat(documentId) {
  return request(`/api/chat/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
}

/** rating: 1 (helpful), -1 (not helpful) or null to remove it. */
export function rateChatMessage(messageId, rating) {
  return request(`/api/chat/messages/${encodeURIComponent(messageId)}/rating`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
}
