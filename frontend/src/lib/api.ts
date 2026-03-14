const API_BASE = "http://localhost:8000";

export async function sendMessage(message: string, history: any[] = []) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!response.ok) throw new Error("Failed to send message");
  return response.json();
}

export async function getAuthStatus() {
  const response = await fetch(`${API_BASE}/auth/status`);
  return response.json();
}

export async function getLoginUrl() {
  const response = await fetch(`${API_BASE}/auth/login`);
  return response.json();
}
