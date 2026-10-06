import { useEffect, useState } from "react";
import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Loader2 } from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
function api(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

type Q = { id: string; label: string; options?: string[]; type?: string };

export function MarketNetworkPage(): JSX.Element {
  const [questions, setQuestions] = useState<Q[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [region, setRegion] = useState("Maharashtra");
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(api("/api/public/market-network/form"), { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setQuestions(d.questions || []))
      .catch(() => setError("Could not load form"));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(api("/api/public/market-network/pulses"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          respondent_role: "broker",
          region,
          email: email || null,
          answers,
        }),
      });
      if (!res.ok) throw new Error("Submit failed");
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <section className="border-b border-[#1e1e1e14] bg-[#161614] text-white">
        <div className="mx-auto max-w-[720px] px-4 py-14 sm:px-8">
          <p className="text-[10px] tracking-[2.6px] text-[#6ee7b7]">MARKET NETWORK</p>
          <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[36px] font-normal sm:text-[44px]">
            Agent &amp; broker pulse
          </h1>
          <p className="mt-4 text-[15px] text-white/50">
            Share what buyers are asking for. WishNest publishes only aggregated intelligence —
            never your individual answers as a public list.
          </p>
        </div>
      </section>
      <section className="mx-auto max-w-[720px] px-4 py-12 sm:px-8">
        {done ? (
          <div className="rounded-2xl border border-[#1e1e1e14] bg-white p-8 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
            <p className="mt-4 text-[22px] [font-family:'Playfair_Display',Helvetica]">Thank you</p>
            <Link href="/">
              <a className="mt-4 inline-block text-emerald-700 underline text-[13px]">Back to WishNest</a>
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-5 rounded-2xl border border-[#1e1e1e14] bg-white p-6 sm:p-8">
            <label className="block text-[12px] text-[#1e1e1e99]">
              Region / state
              <input
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="mt-2 h-11 w-full rounded-md border border-[#1e1e1e22] bg-[#f8f7f4] px-3"
              />
            </label>
            {questions.map((q) => (
              <label key={q.id} className="block text-[12px] text-[#1e1e1e99]">
                {q.label}
                {q.options?.length ? (
                  <select
                    required
                    value={answers[q.id] || ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    className="mt-2 h-11 w-full rounded-md border border-[#1e1e1e22] bg-[#f8f7f4] px-3"
                  >
                    <option value="">Select…</option>
                    {q.options.map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    required
                    value={answers[q.id] || ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    className="mt-2 h-11 w-full rounded-md border border-[#1e1e1e22] bg-[#f8f7f4] px-3"
                  />
                )}
              </label>
            ))}
            <label className="block text-[12px] text-[#1e1e1e99]">
              Email (optional)
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 h-11 w-full rounded-md border border-[#1e1e1e22] bg-[#f8f7f4] px-3"
              />
            </label>
            {error && <p className="text-red-600 text-[13px]">{error}</p>}
            <Button
              type="submit"
              disabled={busy}
              className="h-12 w-full rounded-full bg-[#161614] text-white"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Submit pulse"}
            </Button>
          </form>
        )}
      </section>
      <SiteFooter />
    </main>
  );
}
