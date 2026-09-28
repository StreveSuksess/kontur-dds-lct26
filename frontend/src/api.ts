export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "include",
      headers:
        body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(
      "Нет связи с сервером. Проверьте подключение и повторите действие.",
      0,
    );
  }
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Не удалось выполнить запрос" }));
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : "Проверьте заполнение полей",
      response.status,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Не удалось выполнить действие";
}
export function formatDate(date: string | null) {
  return date
    ? new Date(date).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
}
export function duration(value: number | null | undefined) {
  if (value == null) return "—";
  const n = Math.max(0, Math.floor(value));
  return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
}
