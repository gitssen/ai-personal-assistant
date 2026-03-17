const API_BASE = "http://localhost:8000";

export async function sendMessage(message: string, history: any[] = []) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!response.ok) throw new Error("Failed to send message");
  return response;
}


export async function getAuthStatus() {
  const response = await fetch(`${API_BASE}/auth/status`);
  return response.json();
}

export async function getLoginUrl() {
  const response = await fetch(`${API_BASE}/auth/login`);
  return response.json();
}

export async function logout() {
  const response = await fetch(`${API_BASE}/auth/logout`, { method: "POST" });
  return response.json();
}

export async function getRawMemories(offset: number = 0, limit: number = 50) {
  const response = await fetch(`${API_BASE}/auth/memories/raw?offset=${offset}&limit=${limit}`);
  return response.json();
}

export async function importMemories(facts: string[]) {
  const response = await fetch(`${API_BASE}/auth/memories/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ facts })
  });
  return response.json();
}
