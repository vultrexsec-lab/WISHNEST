import { QueryClient, QueryFunction } from "@tanstack/react-query";
import { getStoredToken, removeToken } from "@/contexts/AuthContext";
import { fetchWithTimeout } from "@/lib/fetchWithTimeout";

// In production static hosts (e.g. Netlify) there's no dev-server proxy for
// /api/*, so we need an absolute backend URL. Set VITE_API_BASE_URL at build
// time to point at the live backend (e.g. Render). Locally/on Replit this is
// left unset and requests stay relative, handled by the Vite proxy.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (API_BASE_URL && path.startsWith("/api")) return `${API_BASE_URL}${path}`;
  return path;
}

async function throwIfResNotOk(res: Response) {
  if (!res.ok) {
    const text = (await res.text()) || res.statusText;
    throw new Error(`${res.status}: ${text}`);
  }
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getStoredToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

/**
 * If the backend returns 401, the stored token is expired or invalid.
 * Clear it and redirect to /login so the user re-authenticates.
 */
function handleUnauthorized() {
  removeToken();
  // Only redirect if we're on a protected page to avoid redirect loops.
  if (!window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

export async function apiRequest(
  method: string,
  url: string,
  data?: unknown,
): Promise<Response> {
  const res = await fetchWithTimeout(apiUrl(url), {
    method,
    headers: authHeaders(data ? { "Content-Type": "application/json" } : {}),
    body: data ? JSON.stringify(data) : undefined,
    credentials: "include",
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

  await throwIfResNotOk(res);
  return res;
}

type UnauthorizedBehavior = "returnNull" | "throw";
export const getQueryFn: <T>(options: {
  on401: UnauthorizedBehavior;
}) => QueryFunction<T> =
  ({ on401: unauthorizedBehavior }) =>
  async ({ queryKey }) => {
    const res = await fetchWithTimeout(apiUrl(queryKey[0] as string), {
      headers: authHeaders(),
      credentials: "include",
    });

    if (res.status === 401) {
      if (unauthorizedBehavior === "returnNull") return null;
      handleUnauthorized();
    }

    await throwIfResNotOk(res);
    return await res.json();
  };

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: getQueryFn({ on401: "throw" }),
      refetchInterval: false,
      refetchOnWindowFocus: false,
      staleTime: Infinity,
      retry: false,
    },
    mutations: {
      retry: false,
    },
  },
});
