import { useMemo, useState } from "react";
import { Link, useRoute } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { Article } from "@/lib/article-types";
import {
  Check,
  Copy,
  Download,
  ExternalLink,
  Loader2,
  Share2,
} from "lucide-react";

function useArticle(id: string | undefined) {
  return useQuery<Article>({
    queryKey: [`/api/articles/${id}`],
    enabled: Boolean(id),
  });
}

function BASlider({ before, after }: { before: string; after: string }) {
  const [pos, setPos] = useState(50);

  return (
    <div className="relative aspect-[16/10] w-full overflow-hidden bg-[#1a1a1a] select-none">
      <img
        src={after}
        alt="After"
        className="absolute inset-0 h-full w-full object-cover"
        referrerPolicy="no-referrer"
        draggable={false}
      />
      <div className="absolute inset-0 overflow-hidden" style={{ width: `${pos}%` }}>
        <img
          src={before}
          alt="Before"
          className="h-full max-w-none object-cover"
          style={{ width: "100vw", maxWidth: "1166px", height: "100%" }}
          referrerPolicy="no-referrer"
          draggable={false}
        />
      </div>
      <div
        className="absolute inset-y-0 w-0.5 bg-white shadow-lg"
        style={{ left: `${pos}%` }}
      >
        <div className="absolute left-1/2 top-1/2 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-[#2e4a3f] text-[10px] font-medium text-white">
          ↔
        </div>
      </div>
      <span className="absolute left-3 top-3 bg-black/50 px-2 py-1 text-[10px] tracking-[1px] text-white">
        BEFORE
      </span>
      <span className="absolute right-3 top-3 bg-black/50 px-2 py-1 text-[10px] tracking-[1px] text-white">
        AFTER
      </span>
      <input
        type="range"
        min={0}
        max={100}
        value={pos}
        onChange={(e) => setPos(Number(e.target.value))}
        className="absolute inset-x-0 bottom-4 z-10 mx-auto w-[70%] accent-white"
        aria-label="Before after slider"
      />
    </div>
  );
}

async function copyText(text: string) {
  await navigator.clipboard.writeText(text);
}

function CopyBtn({ text, label = "Copy" }: { text: string; label?: string }) {
  const { toast } = useToast();
  const [ok, setOk] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="h-8 gap-1.5 rounded-none border-[#2e4a3f]/40 text-[11px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white"
      onClick={async () => {
        try {
          await copyText(text);
          setOk(true);
          toast({ title: "Copied", description: label });
          setTimeout(() => setOk(false), 1500);
        } catch {
          toast({ title: "Copy failed", variant: "destructive" });
        }
      }}
    >
      {ok ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {label}
    </Button>
  );
}

function OwnerSharingPack({ article }: { article: Article }) {
  const snap = (article.property_snapshot || {}) as Record<string, unknown>;
  const originals = Array.isArray(snap.original_photo_urls)
    ? (snap.original_photo_urls as string[])
    : [];
  const afters: string[] = [];
  if (article.hero_image_url) afters.push(article.hero_image_url);
  if (article.section_image_urls) afters.push(...article.section_image_urls.filter(Boolean));

  const origin =
    typeof window !== "undefined" ? window.location.origin : "https://wishnest.info";
  const projectUrl = `${origin}/reimagined/${article.id}`;
  const articleUrl = `${origin}/article/${article.id}`;

  const li =
    article.linkedin_variations?.[0] ||
    `${article.headline}\n\n${article.executive_summary || ""}\n\nRead: ${projectUrl}`;
  const fb =
    article.facebook_variations?.[0] ||
    `${article.headline}\n\n${article.newsletter_summary || article.executive_summary || ""}\n\n${projectUrl}`;
  const xPost =
    article.twitter_thread?.[0] ||
    `${article.headline} — Reimagined™ on WishNest ${projectUrl}`;
  const wa =
    `*${article.headline}*\n\n${article.executive_summary || "Featured on WishNest Reimagined™"}\n\n${projectUrl}`;
  const hashtags = (article.suggested_hashtags || ["#WishNest", "#Reimagined", "#HospitalityDesign"]).join(
    " ",
  );

  const featuredLine = `Featured by WishNest — independent hospitality & architecture editorial. ${projectUrl}`;

  const fullPack = [
    "WISHNEST — OWNER / DEVELOPER SHARING PACK",
    "========================================",
    "",
    `Project: ${article.headline}`,
    article.location ? `Location: ${article.location}` : "",
    "",
    "FEATURED BY WISHNEST",
    featuredLine,
    "",
    "LINKS",
    `Reimagined project: ${projectUrl}`,
    `Full article: ${articleUrl}`,
    "",
    "LINKEDIN",
    li,
    "",
    "INSTAGRAM / FACEBOOK",
    fb,
    "",
    "X (TWITTER)",
    xPost,
    "",
    "WHATSAPP",
    wa,
    "",
    "HASHTAGS",
    hashtags,
    "",
    "ASSETS",
    ...originals.slice(0, 3).map((u, i) => `Before ${i + 1}: ${u}`),
    ...afters.slice(0, 3).map((u, i) => `After ${i + 1}: ${u}`),
    "",
    "Please credit WishNest when sharing. Independent editorial — no paid placements.",
  ]
    .filter((line) => line !== undefined)
    .join("\n");

  const downloadPack = () => {
    const blob = new Blob([fullPack], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `wishnest-share-pack-${article.id.slice(0, 8)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="border-t border-[#1e1e1e14] bg-white">
      <div className="mx-auto max-w-[800px] px-4 py-14 sm:px-8">
        <div className="flex items-center gap-2 text-[#2e4a3f]">
          <Share2 className="h-5 w-5" />
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2px]">
            OWNER / DEVELOPER SHARING PACK
          </p>
        </div>
        <h2 className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[28px] text-[#1e1e1e]">
          Share this feature
        </h2>
        <p className="mt-2 max-w-[520px] text-[14px] leading-[22px] text-[#6b6b6b]">
          Ready-to-post copy, links, and asset references for owners and developers.
          Credit WishNest when you share.
        </p>

        {/* Featured badge */}
        <div className="mt-8 border border-[#2e4a3f]/25 bg-[#f4f7f5] p-6">
          <p className="text-[10px] tracking-[1.6px] text-[#2e4a3f]">FEATURED BY WISHNEST</p>
          <p className="mt-2 [font-family:'Playfair_Display',Helvetica] text-[22px] text-[#1e1e1e]">
            {article.headline}
          </p>
          <p className="mt-2 text-[13px] text-[#6b6b6b]">{featuredLine}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <CopyBtn text={featuredLine} label="Copy featured line" />
            <CopyBtn text={projectUrl} label="Copy project link" />
            <CopyBtn text={articleUrl} label="Copy article link" />
          </div>
        </div>

        <div className="mt-8 space-y-6">
          <PackBlock title="LinkedIn" body={li} />
          <PackBlock title="Instagram / Facebook" body={fb} />
          <PackBlock title="X (Twitter)" body={xPost} />
          <PackBlock title="WhatsApp" body={wa} />
          <PackBlock title="Hashtags" body={hashtags} />
        </div>

        {/* Asset grid */}
        {(originals.length > 0 || afters.length > 0) && (
          <div className="mt-10">
            <p className="text-[10px] tracking-[1.4px] text-[#6b6b6b]">BEFORE / AFTER ASSETS</p>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {originals.slice(0, 3).map((url, i) => (
                <AssetCard key={`b-${i}`} url={url} label={`Before ${i + 1}`} />
              ))}
              {afters.slice(0, 3).map((url, i) => (
                <AssetCard key={`a-${i}`} url={url} label={`After ${i + 1}`} />
              ))}
            </div>
          </div>
        )}

        <div className="mt-10 flex flex-wrap gap-3">
          <Button
            type="button"
            onClick={downloadPack}
            className="h-auto gap-2 rounded-none bg-[#2e4a3f] px-5 py-3 text-[11px] tracking-[1.2px] text-white hover:bg-[#243a32]"
          >
            <Download className="h-3.5 w-3.5" />
            DOWNLOAD FULL PACK (.TXT)
          </Button>
          <CopyBtn text={fullPack} label="Copy full pack" />
          <a href={projectUrl} target="_blank" rel="noopener noreferrer">
            <Button
              variant="outline"
              className="h-auto gap-2 rounded-none border-[#2e4a3f] px-5 py-3 text-[11px] tracking-[1.2px] text-[#2e4a3f]"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Open project page
            </Button>
          </a>
        </div>
      </div>
    </section>
  );
}

function PackBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-[#1e1e1e14] bg-[#f8f7f4] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] tracking-[1.2px] text-[#6b6b6b]">{title.toUpperCase()}</p>
        <CopyBtn text={body} label="Copy" />
      </div>
      <p className="mt-2 whitespace-pre-wrap text-[13px] leading-[22px] text-[#1e1e1e]">{body}</p>
    </div>
  );
}

function AssetCard({ url, label }: { url: string; label: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="group relative block overflow-hidden border border-[#1e1e1e14] bg-[#e8e6e1]"
    >
      <img
        src={url}
        alt={label}
        className="aspect-[4/3] w-full object-cover transition group-hover:opacity-90"
        referrerPolicy="no-referrer"
      />
      <span className="absolute bottom-0 left-0 right-0 bg-black/55 px-2 py-1 text-[10px] tracking-[1px] text-white">
        {label} · open
      </span>
    </a>
  );
}

export function ReimaginedProjectPage(): JSX.Element {
  const [, params] = useRoute("/reimagined/:id");
  const id = params?.id;
  const { data: article, isLoading, error } = useArticle(id);

  const snap = (article?.property_snapshot || {}) as Record<string, unknown>;
  const originals = useMemo(() => {
    const o = snap.original_photo_urls;
    return Array.isArray(o) ? o.map(String) : [];
  }, [snap]);
  const afters = useMemo(() => {
    const list: string[] = [];
    if (article?.hero_image_url) list.push(article.hero_image_url);
    if (article?.section_image_urls)
      list.push(...article.section_image_urls.filter(Boolean));
    return list;
  }, [article]);

  const before = originals[0] || null;
  const after = afters[0] || null;
  const prompt = typeof snap.user_prompt === "string" ? snap.user_prompt : null;

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-32 text-[#6b6b6b]">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading project…
        </div>
      )}

      {error && (
        <div className="mx-auto max-w-[640px] px-4 py-24 text-center">
          <p className="text-[16px] text-[#6b6b6b]">Project not found or not published.</p>
          <Link href="/reimagined">
            <a className="mt-4 inline-block text-[#2e4a3f] hover:underline">
              ← Back to portfolio
            </a>
          </Link>
        </div>
      )}

      {article && (
        <>
          <section className="border-b border-[#1e1e1e14] bg-[#161614] text-white">
            <div className="mx-auto max-w-[1166px] px-4 py-12 sm:px-8 sm:py-16">
              <Link href="/reimagined">
                <a className="text-[12px] text-white/50 hover:text-white">
                  ← Reimagined portfolio
                </a>
              </Link>
              <p className="mt-4 [font-family:'Inter',Helvetica] text-[10px] tracking-[2px] text-[#6ee7b7]">
                REIMAGINED™ PROJECT
              </p>
              <h1 className="mt-3 max-w-[800px] [font-family:'Playfair_Display',Helvetica] text-[32px] leading-tight sm:text-[44px]">
                {article.headline}
              </h1>
              {article.subtitle && (
                <p className="mt-3 max-w-[560px] text-[16px] text-white/60">
                  {article.subtitle}
                </p>
              )}
              {article.location && (
                <p className="mt-4 text-[12px] tracking-[1px] text-white/40">
                  {article.location.toUpperCase()}
                </p>
              )}
            </div>
          </section>

          {before && after && (
            <section className="bg-[#0c0c0c]">
              <div className="mx-auto max-w-[1166px]">
                <BASlider before={before} after={after} />
              </div>
            </section>
          )}

          <section className="mx-auto max-w-[800px] px-4 py-14 sm:px-8">
            {article.executive_summary && (
              <p className="[font-family:'Playfair_Display',Helvetica] text-[20px] leading-[32px] text-[#1e1e1e]">
                {article.executive_summary}
              </p>
            )}
            {prompt && (
              <div className="mt-8 border border-[#1e1e1e14] bg-white p-5">
                <p className="text-[10px] tracking-[1.4px] text-[#6b6b6b]">
                  DESIGN BRIEF / INTERVENTION
                </p>
                <p className="mt-2 text-[14px] leading-[24px] text-[#3a3a3a]">{prompt}</p>
              </div>
            )}
            {article.wishnest_verdict && (
              <div className="mt-8">
                <p className="text-[10px] tracking-[1.4px] text-[#6b6b6b]">WISHNEST VERDICT</p>
                <p className="mt-2 text-[15px] leading-[26px] text-[#1e1e1e]">
                  {article.wishnest_verdict}
                </p>
              </div>
            )}
            {article.full_article && (
              <div
                className="prose prose-neutral mt-10 max-w-none text-[15px] leading-[28px] text-[#3a3a3a]"
                dangerouslySetInnerHTML={{ __html: article.full_article }}
              />
            )}

            {(originals.length > 1 || afters.length > 1) && (
              <div className="mt-14">
                <p className="text-[10px] tracking-[1.4px] text-[#6b6b6b]">MORE VIEWS</p>
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {[...afters.slice(1), ...originals.slice(1)].slice(0, 6).map((url, i) => (
                    <img
                      key={i}
                      src={url}
                      alt=""
                      className="aspect-[4/3] w-full object-cover"
                      referrerPolicy="no-referrer"
                    />
                  ))}
                </div>
              </div>
            )}

            <div className="mt-14 flex flex-wrap gap-3 border-t border-[#1e1e1e14] pt-10">
              <Link href={`/article/${article.id}`}>
                <Button
                  variant="outline"
                  className="rounded-none border-[#2e4a3f] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white"
                >
                  Full article
                </Button>
              </Link>
              <Link href="/get-reviewed">
                <Button className="rounded-none bg-[#2e4a3f] text-white hover:bg-[#243a32]">
                  Get Your Project Reviewed
                </Button>
              </Link>
              <a href="#sharing-pack">
                <Button
                  variant="outline"
                  className="rounded-none border-[#2e4a3f]/50 text-[#2e4a3f]"
                >
                  Owner sharing pack
                </Button>
              </a>
            </div>
          </section>

          <div id="sharing-pack">
            <OwnerSharingPack article={article} />
          </div>
        </>
      )}

      <SiteFooter />
    </main>
  );
}
