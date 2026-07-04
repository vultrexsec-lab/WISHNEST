import { useState, FormEvent } from "react";
import { useLocation } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";

export function LoginPage() {
  const { login } = useAuth();
  const [, navigate] = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      // Clear stale cache so dashboard re-fetches with the new auth token.
      const { queryClient } = await import("@/lib/queryClient");
      queryClient.clear();
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f8f7f4]">
      <div className="w-full max-w-sm border border-[#1e1e1e14] bg-white p-10">
        <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.6px] text-[#2e4a3f]">
          WISHNEST
        </p>
        <h1 className="pt-4 [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal text-[#1e1e1e]">
          Editorial Login
        </h1>
        <p className="pt-1 [font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b]">
          Admin access only.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4">
          <div>
            <label className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">
              USERNAME
            </label>
            <Input
              className="mt-1 rounded-none border-[#1e1e1e1a]"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">
              PASSWORD
            </label>
            <Input
              type="password"
              className="mt-1 rounded-none border-[#1e1e1e1a]"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <p className="[font-family:'Inter',Helvetica] text-[12px] text-red-600">
              {error}
            </p>
          )}

          <Button
            type="submit"
            disabled={loading}
            className="mt-2 h-auto rounded-none bg-[#2e4a3f] px-5 py-3 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.1px] text-white hover:bg-[#243a32]"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "SIGN IN"}
          </Button>
        </form>
      </div>
    </main>
  );
}
