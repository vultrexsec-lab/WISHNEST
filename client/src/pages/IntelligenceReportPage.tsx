import { Link, useRoute } from "wouter";
import { useEffect, useRef, useState } from "react";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";

const META: Record<string, { title: string; src: string; label: string }> = {
  hospitality: {
    title: "Hospitality Project Intelligence",
    src: "/intelligence/hospitality.html",
    label: "Hospitality sample · Riverstone Retreat",
  },
  villa: {
    title: "Villa Project Intelligence",
    src: "/intelligence/villa.html",
    label: "Villa sample · Cedar Ridge Villas",
  },
};

export const IntelligenceReportPage = (): JSX.Element => {
  const [, params] = useRoute("/intelligence/:kind");
  const kind = (params?.kind || "").toLowerCase();
  const meta = META[kind];
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(2400);

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "wishnest-intel-height" && typeof e.data.height === "number") {
        setHeight(Math.max(800, e.data.height));
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  if (!meta) {
    return (
      <main className="min-h-screen bg-[#f8f7f4]">
        <SiteNav />
        <div className="mx-auto max-w-[640px] px-4 py-24 text-center">
          <p className="text-[#6b6b6b]">Report not found.</p>
          <Link href="/intelligence">
            <a className="mt-4 inline-block text-[#2e4a3f] hover:underline">
              ← Intelligence
            </a>
          </Link>
        </div>
        <SiteFooter />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#f4f2ee]">
      <SiteNav />
      <div className="border-b border-[#1e1e1e14] bg-[#f8f7f4] px-4 py-3 sm:px-8">
        <div className="mx-auto flex max-w-[1166px] flex-wrap items-center justify-between gap-3">
          <div>
            <Link href="/intelligence">
              <a className="text-[12px] text-[#6b6b6b] hover:text-[#2e4a3f]">
                ← Intelligence hub
              </a>
            </Link>
            <p className="mt-1 text-[11px] tracking-[1.2px] text-[#2e4a3f]">
              {meta.label}
            </p>
          </div>
          <Link href="/get-reviewed">
            <a className="text-[11px] font-medium tracking-[1px] text-[#2e4a3f] hover:underline">
              Request assessment
            </a>
          </Link>
        </div>
      </div>
      <iframe
        ref={iframeRef}
        title={meta.title}
        src={meta.src}
        className="block w-full border-0"
        style={{ height }}
        onLoad={() => {
          try {
            const doc = iframeRef.current?.contentDocument;
            const h = doc?.documentElement?.scrollHeight || doc?.body?.scrollHeight;
            if (h && h > 400) setHeight(h + 40);
          } catch {
            /* cross-origin not an issue for same-origin public files */
          }
        }}
      />
      <SiteFooter />
    </main>
  );
};
