import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2 } from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function api(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

type Question = {
  id: string;
  label: string;
  type?: string;
  options?: string[];
};

type PublicSurvey = {
  id: string;
  title: string;
  destination: string | null;
  topic: string | null;
  questions: Question[];
};

export function SurveyPublicPage(): JSX.Element {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: survey, isLoading, isError } = useQuery<PublicSurvey>({
    queryKey: ["public-survey", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const res = await fetch(api(`/api/public/surveys/${id}`), { cache: "no-store" });
      if (!res.ok) throw new Error("Survey not found");
      return res.json();
    },
  });

  const questions = useMemo(() => survey?.questions || [], [survey]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(api(`/api/public/surveys/${id}/responses`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim() || null,
          answers,
          consent_commercial: consent,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Submit failed");
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <section className="border-b border-[#1e1e1e14] bg-[#161614] text-white">
        <div className="mx-auto max-w-[720px] px-4 py-14 sm:px-8">
          <p className="text-[10px] font-medium tracking-[2.6px] text-[#6ee7b7]">WISHNEST SURVEY</p>
          {isLoading && <p className="mt-6 text-white/50">Loading…</p>}
          {isError && (
            <p className="mt-6 text-red-300">This survey is closed or does not exist.</p>
          )}
          {survey && (
            <>
              <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[32px] font-normal leading-tight sm:text-[40px]">
                {survey.title}
              </h1>
              {survey.destination && (
                <p className="mt-3 text-[14px] text-white/50">Focus: {survey.destination}</p>
              )}
            </>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-[720px] px-4 py-12 sm:px-8">
        {done ? (
          <div className="rounded-2xl border border-[#1e1e1e14] bg-white p-8 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
            <p className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[24px]">Thank you</p>
            <p className="mt-2 text-[14px] text-[#1e1e1e99]">
              Your response helps WishNest build independent market intelligence.
            </p>
            <Link href="/">
              <a className="mt-6 inline-block text-[13px] text-emerald-700 underline">Back to WishNest</a>
            </Link>
          </div>
        ) : survey ? (
          <form onSubmit={onSubmit} className="space-y-6 rounded-2xl border border-[#1e1e1e14] bg-white p-6 sm:p-8">
            {questions.map((q) => (
              <label key={q.id} className="block">
                <span className="text-[12px] font-medium tracking-[0.5px] text-[#1e1e1e99]">
                  {q.label}
                </span>
                {q.type === "choice" && q.options?.length ? (
                  <select
                    required
                    value={answers[q.id] || ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    className="mt-2 h-11 w-full rounded-md border border-[#1e1e1e22] bg-[#f8f7f4] px-3 text-[14px]"
                  >
                    <option value="">Select…</option>
                    {q.options.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    required
                    value={answers[q.id] || ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    className="mt-2 h-11 w-full rounded-md border border-[#1e1e1e22] bg-[#f8f7f4] px-3 text-[14px]"
                  />
                )}
              </label>
            ))}

            <label className="block">
              <span className="text-[12px] font-medium text-[#1e1e1e99]">Email (optional)</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 h-11 w-full rounded-md border border-[#1e1e1e22] bg-[#f8f7f4] px-3 text-[14px]"
                placeholder="you@example.com"
              />
            </label>

            <label className="flex items-start gap-2 text-[13px] text-[#1e1e1e99]">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-1"
              />
              <span>
                I agree that aggregated, non-identified insights may inform WishNest research and,
                where appropriate, commercial follow-up (ArrowX) with consent.
              </span>
            </label>

            {error && <p className="text-[13px] text-red-600">{error}</p>}

            <Button
              type="submit"
              disabled={submitting}
              className="h-12 w-full rounded-full bg-[#161614] text-[13px] tracking-[1px] text-white hover:bg-[#2a2a28]"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Submit response"}
            </Button>
          </form>
        ) : null}
      </section>
      <SiteFooter />
    </main>
  );
}
