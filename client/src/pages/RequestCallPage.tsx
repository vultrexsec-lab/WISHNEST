import { useState } from "react";
import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { Loader2, Phone } from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function api(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

export function RequestCallPage(): JSX.Element {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(api("/api/public/request-call"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim() || null,
          phone: phone.trim(),
          email: email.trim() || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || `Error ${res.status}`);
      }
      setMsg(data.message || "Request received.");
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0c1210] text-white">
      <SiteNav />
      <main className="mx-auto max-w-lg px-4 py-14">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">
            <Phone className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-medium tracking-tight">Request a short call</h1>
            <p className="text-[13px] text-white/45">WishNest · complimentary listing conversation</p>
          </div>
        </div>

        {done ? (
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-6 text-[14px] leading-relaxed text-emerald-50/90">
            <p className="font-medium text-emerald-200">Thank you</p>
            <p className="mt-2 text-white/70">{msg}</p>
            <Link href="/" className="mt-4 inline-block text-[12px] text-emerald-300/90 underline">
              Back to WishNest
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-[13px] leading-relaxed text-white/50">
              Enter the number where we should call you. By submitting, you agree to receive one short
              call from WishNest about a complimentary property listing. No obligation.
            </p>
            <div>
              <label className="mb-1 block text-[11px] text-white/40">Name (optional)</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px]"
                placeholder="Your name"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-white/40">Phone *</label>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                className="h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px]"
                placeholder="e.g. 9876543210 or +91…"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-white/40">Email (optional)</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px]"
                placeholder="you@email.com"
              />
            </div>
            {error && <p className="text-[12px] text-red-300">{error}</p>}
            <Button
              type="submit"
              disabled={busy || phone.trim().length < 10}
              className="h-10 w-full rounded-full bg-emerald-700 text-[13px] text-white hover:bg-emerald-600"
            >
              {busy ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" /> Connecting…
                </span>
              ) : (
                "Call me now"
              )}
            </Button>
          </form>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
