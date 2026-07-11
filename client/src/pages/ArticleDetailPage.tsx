import { useParams, Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Loader2 } from "lucide-react";
import {
  ABCDE_GRADES,
  ABCDE_SCORES,
  Article,
  formatDate,
  overallGrade,
} from "@/lib/article-types";

export const ArticleDetailPage = (): JSX.Element => {
  const { id } = useParams<{ id: string }>();

  const {
    data: article,
    isLoading,
    isError,
  } = useQuery<Article>({
    queryKey: [`/api/articles/${id}`],
  });

  if (isLoading) {
    return (
      <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
        <SiteNav />
        <div className="flex items-center justify-center gap-2 py-40 text-[#6b6b6b]">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="[font-family:'Inter',Helvetica] text-[13px]">
            Loading article…
          </span>
        </div>
      </main>
    );
  }

  if (isError || !article) {
    return (
      <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
        <SiteNav />
        <div className="mx-auto flex max-w-[600px] flex-col items-center gap-4 py-40 text-center">
          <h1 className="[font-family:'Playfair_Display',Helvetica] text-[28px] text-[#1e1e1e]">
            Article not found
          </h1>
          <p className="[font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b]">
            This article may not exist, or hasn't been generated yet.
          </p>
          <Link href="/dashboard">
            <span className="cursor-pointer [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1px] text-[#2e4a3f] hover:opacity-70">
              ← Back to review dashboard
            </span>
          </Link>
        </div>
        <SiteFooter />
      </main>
    );
  }

  const grade = overallGrade(article);
  const isReview = article.article_type === "review";
  const snapshot =
    (article.property_snapshot as Record<string, string | number>) ?? {};
  const snapshotEntries = Object.entries(snapshot);

  return (
    <main className="w-full max-w-full overflow-x-hidden bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      {/* Hero */}
      <section
        className="relative overflow-hidden bg-[#1a1a1a]"
        style={
          article.hero_image_url
            ? {
                backgroundImage: `url(${article.hero_image_url})`,
                backgroundSize: "cover",
                backgroundPosition: "center",
              }
            : undefined
        }
      >
        <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(20,20,20,0.95)_0%,rgba(20,20,20,0.6)_60%,rgba(0,0,0,0.3)_100%)]" />
        <div className="relative mx-auto flex min-h-[280px] w-full max-w-[1166px] flex-col justify-end px-4 pb-10 pt-8 sm:min-h-[380px] sm:px-8 sm:pb-16">
          <div className="mb-4 inline-flex w-fit items-center gap-3">
            {article.location && (
              <div className="bg-[#2e4a3f] px-3 py-[7px]">
                <span className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1.40px] text-white">
                  {article.location.toUpperCase()}
                </span>
              </div>
            )}
            <span className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#ffffff80]">
              {isReview ? "PROPERTY REVIEW" : "EDITORIAL"}
            </span>
          </div>
          <h1
            className="[font-family:'Playfair_Display',Helvetica] text-[28px] font-normal leading-[1.15] text-white sm:text-[40px] lg:text-[56px]"
            data-testid="text-article-headline"
          >
            {article.headline}
          </h1>
          {article.subtitle && (
            <p className="max-w-[640px] pt-5 [font-family:'Inter',Helvetica] text-[16px] font-normal leading-[28px] text-[#ffffffb2]">
              {article.subtitle}
            </p>
          )}
          <p className="pt-6 [font-family:'Inter',Helvetica] text-[11px] text-[#ffffff66]">
            {formatDate(article.created_at)}
          </p>
        </div>
      </section>

      {/* Snapshot stats */}
      {snapshotEntries.length > 0 && (
        <section className="border-b border-[#1e1e1e1a] bg-white">
          <div className="mx-auto w-full max-w-[1166px] px-4 py-6 sm:px-8 sm:py-8">
            <div className="grid grid-cols-2 gap-4 gap-y-6 sm:gap-6 md:grid-cols-4 lg:grid-cols-6">
              {snapshotEntries.map(([key, value]) => (
                <div key={key}>
                  <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
                    {key.replace(/_/g, " ").toUpperCase()}
                  </div>
                  <div className="pt-1 [font-family:'Inter',Helvetica] text-[14px] font-normal text-[#1e1e1e]">
                    {String(value)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Main content */}
      <section className="py-10 sm:py-16 md:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-6 md:px-8">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,680px)_280px] lg:gap-16">
            {/* min-w-0 is critical: without it, CSS grid children keep min-width:auto
                and overflow their column boundary, pushing content off-screen on mobile */}
            <div className="min-w-0">
              {article.executive_summary && (
                <p className="pb-8 [font-family:'Inter',Helvetica] text-[17px] font-normal italic leading-[30px] text-[#2e4a3f]">
                  {article.executive_summary}
                </p>
              )}

              {article.section_image_urls &&
                article.section_image_urls.some(Boolean) && (
                  <div className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {article.section_image_urls
                      .map((url, originalIdx) => ({
                        url,
                        caption: article.captions?.[originalIdx],
                      }))
                      .filter(({ url }) => !!url)
                      .map(({ url, caption }, i) => (
                        <div key={i}>
                          <img
                            src={url}
                            alt={caption || `Section ${i + 1} — ${article.headline}`}
                            loading="lazy"
                            referrerPolicy="no-referrer"
                            className="h-[160px] w-full rounded-lg object-cover"
                          />
                          {caption && (
                            <p className="mt-1.5 [font-family:'Inter',Helvetica] text-[11px] italic text-[#6b6b6b]">
                              {caption}
                            </p>
                          )}
                        </div>
                      ))}
                  </div>
                )}

              {article.full_article && (
                <div
                  data-testid="text-article-body"
                  className="article-body [font-family:'Inter',Helvetica] text-[15px] font-normal leading-[26px] text-[#1e1e1e] sm:text-[17px] sm:leading-[30px]
                    [&_h2]:mt-10 [&_h2]:[font-family:'Playfair_Display',Helvetica] [&_h2]:text-[22px] [&_h2]:font-normal [&_h2]:text-[#1e1e1e] sm:[&_h2]:mt-12 sm:[&_h2]:text-[26px]
                    [&_h3]:mt-6 [&_h3]:[font-family:'Playfair_Display',Helvetica] [&_h3]:text-[18px] [&_h3]:font-normal [&_h3]:text-[#1e1e1e] sm:[&_h3]:mt-8 sm:[&_h3]:text-[20px]
                    [&_p]:pt-5 [&_p:first-child]:pt-0 sm:[&_p]:pt-6
                    [&_ul]:mt-4 [&_ul]:space-y-2 [&_ul]:pl-5 [&_ul]:list-disc
                    [&_ol]:mt-4 [&_ol]:space-y-2 [&_ol]:pl-5 [&_ol]:list-decimal
                    [&_li]:text-[14px] [&_li]:leading-[24px] [&_li]:text-[#1e1e1e] sm:[&_li]:text-[16px] sm:[&_li]:leading-[28px]
                    [&_img]:h-auto [&_img]:w-full [&_img]:object-cover [&_figure]:!mx-0
                    [&_table]:mt-8 [&_table]:min-w-[520px] [&_table]:w-full [&_table]:border-collapse [&_table]:text-[13px] sm:[&_table]:min-w-0 sm:[&_table]:text-[14px]
                    [&_th]:border [&_th]:border-[#1e1e1e1a] [&_th]:bg-[#2e4a3f] [&_th]:text-white [&_th]:px-3 [&_th]:py-2.5 [&_th]:text-left [&_th]:[font-family:'Inter',Helvetica] [&_th]:text-[10px] [&_th]:tracking-[0.8px] [&_th]:font-medium sm:[&_th]:px-4 sm:[&_th]:py-3 sm:[&_th]:text-[11px]
                    [&_td]:border [&_td]:border-[#1e1e1e1a] [&_td]:px-3 [&_td]:py-2.5 [&_td]:align-top [&_td]:leading-[20px] sm:[&_td]:px-4 sm:[&_td]:py-3 sm:[&_td]:leading-[22px]
                    [&_tr:nth-child(even)_td]:bg-[#f8f7f4]
                    [&_br]:block [&_br]:mt-4"
                >
                  {/* overflow-x-auto scopes table scroll; the outer article-body
                      div inherits min-w-0 from the grid child so long prose
                      lines wrap instead of forcing the column wider */}
                  <div className="min-w-0 overflow-x-auto">
                    <div
                      className="min-w-0"
                      dangerouslySetInnerHTML={{ __html: article.full_article }}
                    />
                  </div>
                </div>
              )}

              {article.pull_quotes && article.pull_quotes.length > 0 && (
                <div className="mt-12 space-y-6 border-l-2 border-[#2e4a3f] pl-6">
                  {article.pull_quotes.map((quote, i) => (
                    <p
                      key={i}
                      className="[font-family:'Playfair_Display',Helvetica] text-[22px] italic leading-[32px] text-[#2e4a3f]"
                    >
                      "{quote}"
                    </p>
                  ))}
                </div>
              )}

              {article.faq_section && article.faq_section.length > 0 && (
                <div className="mt-16 border-t border-[#1e1e1e1a] pt-10">
                  <h2 className="[font-family:'Playfair_Display',Helvetica] text-[26px] font-normal text-[#1e1e1e]">
                    Frequently Asked Questions
                  </h2>
                  <div className="mt-6 space-y-6">
                    {article.faq_section.map((faq, i) => (
                      <div key={i}>
                        <p className="[font-family:'Inter',Helvetica] text-[15px] font-medium text-[#1e1e1e]">
                          {faq.question}
                        </p>
                        <p className="pt-2 [font-family:'Inter',Helvetica] text-[14px] leading-[24px] text-[#6b6b6b]">
                          {faq.answer}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-16 border-t border-[#1e1e1e1a] pt-10">
                <Link href="/dashboard">
                  <button className="[font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.10px] text-[#2e4a3f] transition-opacity hover:opacity-70">
                    ← Back to review dashboard
                  </button>
                </Link>
              </div>
            </div>

            {/* Sidebar */}
            <aside className="min-w-0 lg:pt-2">
              <div className="sticky top-24 space-y-8">
                {grade && (
                  <div className="bg-white p-8">
                    <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#6b6b6b]">
                      ABCDE™ SCORE BREAKDOWN
                    </div>
                    <div className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[52px] font-normal leading-[52px] text-[#2e4a3f]">
                      {grade}
                    </div>
                    <div className="mt-6 space-y-3">
                      {ABCDE_GRADES.map((g) => {
                        const value = article[g.key] as string | null;
                        if (!value) return null;
                        return (
                          <div
                            key={g.key}
                            className="flex items-center gap-2"
                          >
                            {/* Letter — fixed width so all letters stack flush left */}
                            <span className="w-3 flex-shrink-0 [font-family:'Inter',Helvetica] text-xs font-bold text-[#2e4a3f]">
                              {g.letter}
                            </span>
                            {/* Title — takes remaining space, truncates if very long */}
                            <span className="min-w-0 flex-1 truncate [font-family:'Inter',Helvetica] text-[10px] text-[#6b6b6b]">
                              {g.title}
                            </span>
                            {/* Grade value — fixed width, always right-aligned so all grades stack flush right */}
                            <span className="w-7 flex-shrink-0 text-right [font-family:'Inter',Helvetica] text-xs font-medium text-[#2e4a3f]">
                              {value}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {!!(article.best_for?.length || article.not_ideal_for?.length) && (
                  <div className="bg-white p-8">
                    {article.best_for && article.best_for.length > 0 && (
                      <div className="pb-5">
                        <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#6b6b6b]">
                          BEST FOR
                        </div>
                        <ul className="mt-2 space-y-1">
                          {article.best_for.map((b, i) => (
                            <li
                              key={i}
                              className="[font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]"
                            >
                              · {b}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {article.not_ideal_for && article.not_ideal_for.length > 0 && (
                      <div>
                        <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#6b6b6b]">
                          NOT IDEAL FOR
                        </div>
                        <ul className="mt-2 space-y-1">
                          {article.not_ideal_for.map((b, i) => (
                            <li
                              key={i}
                              className="[font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]"
                            >
                              · {b}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {article.keywords && article.keywords.length > 0 && (
                  <div className="bg-white p-8">
                    <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#6b6b6b]">
                      KEYWORDS
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {article.keywords.map((k, i) => (
                        <span
                          key={i}
                          className="border border-[#1e1e1e14] px-2 py-1 [font-family:'Inter',Helvetica] text-[10px] text-[#6b6b6b]"
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* ABCDE™ Numeric Score Card — visible when LLM-generated scores exist */}
                {ABCDE_SCORES.some(({ scoreKey }) => article[scoreKey] != null) && (
                  <div className="overflow-hidden bg-[#1a2e28]">
                    {/* Header */}
                    <div className="flex items-end justify-between px-6 pb-4 pt-6">
                      <div>
                        <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[2px] text-[#ffffff66]">
                          ABCDE™ SCORE
                        </div>
                        <div className="mt-0.5 [font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.4px] text-[#ffffff40]">
                          WISHNEST RATING FRAMEWORK
                        </div>
                      </div>
                      {article.abcde_overall && (
                        <div className="[font-family:'Playfair_Display',Helvetica] text-[44px] font-normal leading-none text-white">
                          {article.abcde_overall}
                        </div>
                      )}
                    </div>

                    {/* Thin rule */}
                    <div className="mx-6 border-t border-[#ffffff14]" />

                    {/* Score rows */}
                    <div className="space-y-5 px-6 pb-6 pt-5">
                      {ABCDE_SCORES.map(({ scoreKey, letter, title }) => {
                        const score = article[scoreKey] as number | null;
                        if (score == null) return null;
                        const pct = Math.round((score / 10) * 100);
                        return (
                          <div key={String(scoreKey)}>
                            <div className="mb-2 flex items-center justify-between">
                              <div className="flex items-center gap-2.5">
                                {/* Letter badge */}
                                <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center border border-[#ffffff30]">
                                  <span className="[font-family:'Inter',Helvetica] text-[9px] font-bold text-[#ffffffb3]">
                                    {letter}
                                  </span>
                                </div>
                                <span className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-none text-[#ffffffb3]">
                                  {title}
                                </span>
                              </div>
                              <span className="[font-family:'Playfair_Display',Helvetica] text-[15px] font-normal text-white">
                                {score.toFixed(1)}
                              </span>
                            </div>
                            {/* Track */}
                            <div className="h-px w-full overflow-hidden bg-[#ffffff14]">
                              <div
                                className="h-full bg-[#ffffff80] transition-all"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Footer note */}
                    <div className="border-t border-[#ffffff0a] px-6 py-3">
                      <p className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[14px] text-[#ffffff33]">
                        Scored across architecture, landscape, connectivity,
                        guest delight & eat/explore. All scores 1–10.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </aside>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
