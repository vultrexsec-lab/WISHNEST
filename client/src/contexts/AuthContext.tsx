import { createContext, useContext, useState, ReactNode } from "react";
import { fetchWithTimeout } from "@/lib/fetchWithTimeout";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
function loginUrl(): string {
  return API_BASE_URL ? `${API_BASE_URL}/api/auth/login` : "/api/auth/login";
}

const TOKEN_KEY = "wishnest_admin_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

interface AuthContextType {
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken());

  const login = async (username: string, password: string) => {
    // Uses fetchWithTimeout (2 min timeout + one silent retry) so a cold
    // Render backend spinning up doesn't make the first login attempt look
    // like it hung — it now waits it out and retries once automatically.
    const res = await fetchWithTimeout(loginUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      let detail = "Login failed";
      try {
        const body = await res.json();
        detail = body.detail ?? detail;
      } catch {}
      throw new Error(detail);
    }
    const data = await res.json();
    storeToken(data.access_token);
    setToken(data.access_token);
  };

  const logout = () => {
    removeToken();
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ isAdmin: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
