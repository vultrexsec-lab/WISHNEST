import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";

export default function NotFound() {
  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <div className="mx-auto flex max-w-[560px] flex-col items-center gap-5 px-4 py-32 text-center">
        <p className="[font-family:'Inter',Helvetica] text-[11px] tracking-[2px] text-[#6b6b6b]">
          404
        </p>
        <h1 className="[font-family:'Playfair_Display',Helvetica] text-[28px] leading-tight text-[#1e1e1e]">
          Page not found
        </h1>
        <p className="[font-family:'Inter',Helvetica] text-[14px] leading-relaxed text-[#6b6b6b]">
          This address is not part of the public WishNest site, or the link is out of date.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
          <Link href="/">
            <span className="cursor-pointer [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.2px] text-[#2e4a3f] underline-offset-4 hover:underline">
              Home
            </span>
          </Link>
          <Link href="/reviews">
            <span className="cursor-pointer [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.2px] text-[#2e4a3f] underline-offset-4 hover:underline">
              Reviews
            </span>
          </Link>
          <Link href="/get-reviewed">
            <span className="cursor-pointer [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.2px] text-[#2e4a3f] underline-offset-4 hover:underline">
              Get Reviewed
            </span>
          </Link>
        </div>
      </div>
      <SiteFooter />
    </main>
  );
}
