import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { Menu, X, Search } from "lucide-react";
import { SearchModal } from "@/components/SearchModal";
import { NewsletterModal } from "@/components/NewsletterModal";

const navLinks = [
  { label: "REVIEWS", href: "/reviews" },
  { label: "DESTINATIONS", href: "/destinations" },
  { label: "BEST OF", href: "/best-of" },
  { label: "INTELLIGENCE", href: "/intelligence" },
  { label: "CONTRIBUTORS", href: "/contributors" },
  { label: "REIMAGINED™", href: "/reimagined" },
  { label: "DASHBOARD", href: "/dashboard" },
];

export const SiteNav = () => {
  const [location] = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [newsletterOpen, setNewsletterOpen] = useState(false);

  return (
    <>
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
      <NewsletterModal open={newsletterOpen} onClose={() => setNewsletterOpen(false)} />

      <header className="sticky top-0 z-50 border-b border-[#1e1e1e14] bg-[#f8f7f4]/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1166px] items-center justify-between gap-4 px-4 py-4 sm:px-8 sm:py-5">
          <Link href="/">
            <div className="flex min-w-0 cursor-pointer flex-col">
              <div className="[font-family:'Playfair_Display',Helvetica] text-[22px] font-bold leading-[22px] tracking-[3px] text-[#1e1e1e] sm:text-[26px] sm:leading-[26px] sm:tracking-[3.90px]">
                WISHNEST
              </div>
              <div className="hidden pt-0.5 [font-family:'Inter',Helvetica] text-[9px] font-normal leading-[9px] tracking-[1.80px] text-[#6b6b6b] sm:block">
                HOSPITALITY · ARCHITECTURE · SECOND HOME INTELLIGENCE
              </div>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden items-center gap-5 lg:flex" aria-label="Primary">
            {navLinks.map((item) => (
              <Link key={item.label} href={item.href}>
                <span
                  className={`cursor-pointer whitespace-nowrap [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.10px] transition-opacity hover:opacity-70 ${
                    location === item.href ? "text-[#2e4a3f]" : "text-[#1e1e1e]"
                  }`}
                >
                  {item.label}
                </span>
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Search icon */}
            <button
              onClick={() => setSearchOpen(true)}
              className="flex h-9 w-9 items-center justify-center text-[#1e1e1e] transition-opacity hover:opacity-60"
              aria-label="Search"
            >
              <Search className="h-[18px] w-[18px]" />
            </button>

            {/* Newsletter — hidden on small mobile */}
            <Button
              variant="outline"
              onClick={() => setNewsletterOpen(true)}
              className="hidden h-auto rounded-none border-[0.8px] border-[#2e4a3f] bg-transparent px-4 py-2 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white sm:inline-flex sm:px-5 sm:py-2.5"
            >
              NEWSLETTER
            </Button>

            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="flex h-9 w-9 items-center justify-center text-[#1e1e1e] lg:hidden"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile slide-down menu */}
        {mobileOpen && (
          <div className="border-t border-[#1e1e1e14] bg-[#f8f7f4] px-4 pb-6 pt-2 lg:hidden">
            <nav className="flex flex-col" aria-label="Mobile navigation">
              {navLinks.map((item) => (
                <Link key={item.label} href={item.href}>
                  <span
                    onClick={() => setMobileOpen(false)}
                    className={`block cursor-pointer border-b border-[#1e1e1e0a] py-3.5 [font-family:'Inter',Helvetica] text-[13px] font-medium tracking-[1.10px] transition-opacity hover:opacity-70 ${
                      location === item.href ? "text-[#2e4a3f]" : "text-[#1e1e1e]"
                    }`}
                  >
                    {item.label}
                  </span>
                </Link>
              ))}
              <div className="pt-5">
                <Button
                  variant="outline"
                  onClick={() => { setMobileOpen(false); setNewsletterOpen(true); }}
                  className="h-auto w-full rounded-none border-[0.8px] border-[#2e4a3f] bg-transparent py-3 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.32px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white"
                >
                  NEWSLETTER
                </Button>
              </div>
            </nav>
          </div>
        )}
      </header>
    </>
  );
};
