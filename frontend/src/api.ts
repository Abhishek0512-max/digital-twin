const API_BASE = "http://localhost:8000";

export interface StreamMeta {
  conversation_id: string;
  message_id: string;
}

export interface SourceInfo {
  file: string;
  section: string;
  score: number;
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  onMeta: (meta: StreamMeta) => void,
  onToken: (token: string) => void,
  onSources: (sources: SourceInfo[]) => void,
  onDone: () => void,
  onError: (err: Error) => void,
) {
  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No reader available");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = JSON.parse(line.slice(6));
        if (data.type === "meta") onMeta(data);
        else if (data.type === "token") onToken(data.content);
        else if (data.type === "sources") onSources(data.sources || []);
        else if (data.type === "done") onDone();
      }
    }
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

export async function sendFeedback(payload: {
  message_id: string;
  conversation_id: string;
  question: string;
  response: string;
  rating: "up" | "down";
  comment?: string;
}) {
  await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function runEval(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/eval/run`, { method: "POST" });
  return res.json();
}

export async function getEvalResults(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/eval/results`);
  return res.json();
}
