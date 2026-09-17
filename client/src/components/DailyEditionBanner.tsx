import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Clock3, Sparkles } from "lucide-react";
import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import type { Article } from "@/lib/article-types";

interface DailyEditorialStatus {
  enabled: boolean;
  daily_time: string;
  timezone: string;
  next_run_at: string;
  last_ready_date: string | null;
  latest_article: {
    id: string;
    headline: string;
    category: string | null;
    hero_image_url: string | null;
    published_at: string;
  } | null;
}

interface DailyEditionBannerProps {
  latestArticle?: Article;
}

function formatTimezone(timezone: string): string {
  if (timezone === "Asia/Kolkata") return "IST";
  return timezone.split("/").pop()?.replace(/_/g, " ") ?? timezone;
}

function formatCountdown(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  return `${hours}h ${minutes}m`;
}

export function DailyEditionBanner({ latestArticle }: DailyEditionBannerProps): JSX.Element {
  const { data, isLoading } = useQuery<DailyEditorialStatus>({
    queryKey: ["/api/editorial/daily"],
    refetchInterval: 60_000,
    retry: 1,
  });
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const countdown = useMemo(() => {
    if (!data?.next_run_at) return null;
    return formatCountdown(new Date(data.next_run_at).getTime() - now);
  }, [data?.next_run_at, now]);

  const article = latestArticle ?? undefined;
  const timeLabel = data
    ? `${data.daily_time} ${formatTimezone(data.timezone)}`
    : "08:00 IST";

  return (
    <section className="border-y border-[#ffffff1f] bg-[#213c34] text-white">
      <div className="mx-auto grid w-full max-w-[1166px] gap-8 px-4 py-8 sm:px-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center lg:py-10">
        <div>
          <div className="flex items-center gap-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.4px] text-[#c9d8cf]">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            THE DAILY EDITION
            <span className="h-px w-10 bg-[#ffffff45]" />
          </div>
          <h2 className="max-w-[620px] pt-3 [font-family:'Playfair_Display',Helvetica] text-[29px] font-normal leading-[1.08] sm:text-[38px]">
            One considered story, prepared every day.
          </h2>
          <p className="max-w-[600px] pt-3 [font-family:'Inter',Helvetica] text-[14px] leading-6 text-[#ffffffb8]">
            A fresh WishNest draft is prepared daily and appears here after editorial approval.
            No rushed publishing. Just a better story, one day at a time.
          </p>
          <div className="flex flex-wrap gap-3 pt-6">
            <div className="inline-flex items-center gap-2 border border-[#ffffff38] px-3 py-2 [font-family:'Inter',Helvetica] text-[10px] tracking-[1.2px] text-[#ffffffd4]">
              <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
              NEXT EDITION {isLoading ? "—" : timeLabel}
            </div>
            {countdown && data?.enabled && (
              <div className="inline-flex items-center border border-[#d8b98b66] bg-[#d8b98b18] px-3 py-2 [font-family:'Inter',Helvetica] text-[10px] tracking-[1.2px] text-[#f0d9b3]">
                IN {countdown}
              </div>
            )}
          </div>
        </div>
        <div className="border-t border-[#ffffff26] pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          {article ? (
            <Link href={`/article/${article.id}`}>
              <article className="group flex items-center gap-4">
                <div className="h-20 w-24 shrink-0 overflow-hidden bg-[#ffffff14]">
                  {article.hero_image_url ? (
                    <img
                      src={article.hero_image_url}
                      alt=""
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center [font-family:'Playfair_Display',Helvetica] text-sm italic text-[#ffffff66]">
                      WN
                    </div>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="[font-family:'Inter',Helvetica] text-[9px] tracking-[1.7px] text-[#c9d8cf]">
                    LATEST APPROVED STORY
                  </div>
                  <h3 className="line-clamp-2 pt-1 [font-family:'Playfair_Display',Helvetica] text-[19px] leading-6 text-white">
                    {article.headline}
                  </h3>
                  <div className="flex items-center gap-1 pt-2 [font-family:'Inter',Helvetica] text-[10px] tracking-[1px] text-[#ffffff9c]">
                    READ STORY <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                  </div>
                </div>
              </article>
            </Link>
          ) : (
            <div className="[font-family:'Inter',Helvetica] text-[13px] leading-6 text-[#ffffffa8]">
              The next edition is in preparation. Check back after the first story is approved.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}