export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8765").replace(/\/$/, "");

/** An API failure carrying a sentence that is safe to show to the developer. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly runId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const OFFLINE_MESSAGE =
  "We couldn’t reach the ForgeFlow API. Start it with “uv run forgeflow serve” and try again.";

function fallbackMessage(status: number): string {
  if (status === 404) return "We couldn’t find that. It may have been removed or renamed.";
  if (status === 409) return "Something else is already changing this. Wait a moment and try again.";
  if (status >= 500) return "The ForgeFlow API ran into a problem. Check its terminal for details, then try again.";
  return "The ForgeFlow API didn’t accept that request. Check the details and try again.";
}

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  // FastAPI request-validation errors arrive as a list of {loc, msg}.
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : null))
      .filter(Boolean)
      .map((msg) => {
        const text = String(msg);
        return text.charAt(0).toUpperCase() + text.slice(1).replace(/\.?$/, ".");
      })
      .join(" ");
  }
  return null;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    });
  } catch {
    throw new ApiError(OFFLINE_MESSAGE, 0);
  }
  if (!response.ok) {
    let message = fallbackMessage(response.status);
    let runId: string | undefined;
    try {
      const body = await response.json();
      message = detailToMessage(body.detail) || message;
      runId = typeof body.run_id === "string" ? body.run_id : undefined;
    } catch {
      /* non-JSON error body: keep the generic sentence */
    }
    throw new ApiError(message, response.status, runId);
  }
  return (await response.json()) as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}

export const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
export const patch = (body: unknown): RequestInit => ({ method: "PATCH", body: JSON.stringify(body) });
