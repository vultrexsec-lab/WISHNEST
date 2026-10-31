import { ArrowUpRight, BookOpen } from "lucide-react";
import { Link } from "wouter";
import type { Article } from "@/lib/article-types";
import { resolveMediaUrl } from "@/lib/mediaUrl";
import { formatDate } from "@/lib/article-types";

interface DailyEditionBannerProps {
  latestArticle?: Article;
}

/**
 * Honest publishing strip: show latest published story when available.
 * Does not promise a daily drop if none is ready.
 */
export function DailyEditionBanner({ latestArticle }: DailyEditionBannerProps): JSX.Element {
  const article = latestArticle;

  return (
    <section className="border-y border-[#ffffff1f] bg-[#213c34] text-white">
      <div className="mx-auto grid w-full max-w-[1166px] gap-8 px-4 py-8 sm:px-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center lg:py-10">
        <div>
          <div className="flex items-center gap-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.4px] text-[#c9d8cf]">
            <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
            FROM THE EDITORS
          </div>
          <h2 className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[26px] font-normal leading-[1.2] sm:text-[32px]">
            {article ? "Latest published story" : "Stories, published regularly"}
          </h2>
          <p className="mt-3 max-w-[520px] text-[14px] leading-[24px] text-[#c9d8cf]/90">
            {article
              ? "A considered piece from the WishNest library — not a sponsored placement."
              : "We publish independent reviews and intelligence when pieces meet editorial standard — not on an empty countdown."}
          </p>
          {article && (
            <p className="mt-2 text-[11px] tracking-[1px] text-[#c9d8cf]/70">
              {article.location ? `${article.location} · ` : ""}
              {article.created_at ? formatDate(article.created_at) : ""}
            </p>
          )}
        </div>
        <div className="border border-white/15 bg-[#1a3029] p-5">
          {article ? (
            <Link href={`/article/${article.id}`}>
              <div className="group cursor-pointer">
                {article.hero_image_url && (
                  <div
                    className="mb-4 aspect-[16/9] bg-cover bg-center"
                    style={{ backgroundImage: `url(${resolveMediaUrl(article.hero_image_url)})` }}
                  />
                )}
                <p className="text-[10px] tracking-[1.5px] text-[#c9d8cf]/80">
                  {(article.category || "EDITORIAL").toString().toUpperCase()}
                </p>
                <p className="mt-2 [font-family:'Playfair_Display',Helvetica] text-[18px] leading-[26px] group-hover:underline">
                  {article.headline}
                </p>
                <span className="mt-4 inline-flex items-center gap-1 text-[11px] tracking-[1px] text-[#6ee7b7]">
                  READ STORY <ArrowUpRight className="h-3.5 w-3.5" />
                </span>
              </div>
            </Link>
          ) : (
            <div>
              <p className="text-[14px] leading-[24px] text-[#c9d8cf]">
                Browse the library while the next piece is in preparation.
              </p>
              <Link href="/reviews">
                <span className="mt-4 inline-flex cursor-pointer items-center gap-1 text-[11px] tracking-[1px] text-[#6ee7b7]">
                  EXPLORE REVIEWS <ArrowUpRight className="h-3.5 w-3.5" />
                </span>
              </Link>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
