/**
 * fetch wrapper with an explicit timeout + one automatic silent retry.
 *
 * Why: the Render backend free/starter instance spins down when idle, so the
 * very first request after a period of inactivity (login, or the first
 * "generate article" click) has to wait for a cold start that can take
 * 30-60+ seconds. Two problems used to compound this:
 *   1. Plain `fetch()` has no explicit timeout, so a request can appear to
 *      hang indefinitely with no feedback and no recovery path.
 *   2. If a request *did* fail (network blip, proxy timeout) while Render
 *      was mid-boot, there was no retry — the user had to manually resubmit,
 *      which is why "the second attempt loads instantly" (Render was warm
 *      by then).
 *
 * This wrapper gives requests a generous 2-minute timeout (long enough to
 * outlast a Render cold start) and automatically retries once on timeout or
 * network failure, so a cold start is invisible to the user instead of
 * looking like a stuck/broken request.
 */

export const DEFAULT_TIMEOUT_MS = 120_000; // 2 minutes

export class FetchTimeoutError extends Error {
  constructor(message = "Request timed out.") {
    super(message);
    this.name = "FetchTimeoutError";
  }
}

async function fetchOnce(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new FetchTimeoutError(
        "The server took too long to respond (it may be waking up — please try again).",
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * fetch() with a `timeoutMs` cap (default 2 minutes) and one automatic retry
 * if the first attempt times out or fails at the network level. Retried
 * requests wait briefly before resubmitting so a just-woken backend has a
 * moment to settle.
 */
export async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  try {
    return await fetchOnce(url, init, timeoutMs);
  } catch (err) {
    const isTimeout = err instanceof FetchTimeoutError;
    const isNetworkError = err instanceof TypeError;
    if (!isTimeout && !isNetworkError) throw err;

    // Brief pause, then a single silent retry — by now the backend has had
    // extra time to finish spinning up.
    await new Promise((resolve) => setTimeout(resolve, 1500));
    return fetchOnce(url, init, timeoutMs);
  }
}

/**
 * Fire-and-forget request to wake a cold Render instance as early as
 * possible (e.g. as soon as the login page mounts), so by the time the user
 * finishes typing their credentials the backend is likely already warm.
 */
export function warmUpBackend(apiBaseUrl: string): void {
  const url = apiBaseUrl ? `${apiBaseUrl.replace(/\/$/, "")}/api/health` : "/api/health";
  fetch(url, { method: "GET" }).catch(() => {
    /* best-effort warm-up ping; ignore failures */
  });
}
