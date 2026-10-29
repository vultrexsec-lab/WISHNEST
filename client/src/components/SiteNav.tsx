import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { Menu, X, Search, ChevronDown } from "lucide-react";
import { SearchModal } from "@/components/SearchModal";
import { NewsletterModal } from "@/components/NewsletterModal";

const navLinks = [
  { label: "REVIEWS", href: "/reviews" },
  { label: "DESTINATIONS", href: "/destinations" },
  { label: "BEST OF", href: "/best-of" },
  {
    label: "INTELLIGENCE",
    href: "/intelligence",
    children: [
      { label: "Overview", href: "/intelligence" },
      { label: "Hospitality Intelligence", href: "/intelligence/hospitality" },
      { label: "Villa Intelligence", href: "/intelligence/villa" },
    ],
  },
  { label: "CONTRIBUTORS", href: "/contributors" },
  { label: "REIMAGINED™", href: "/reimagined" },
  { label: "GET REVIEWED", href: "/get-reviewed" },
];

export const SiteNav = () => {
  const [location] = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [newsletterOpen, setNewsletterOpen] = useState(false);
  const [intelOpen, setIntelOpen] = useState(false);

  const isActive = (href: string) =>
    location === href || (href !== "/" && location.startsWith(href + "/"));

  return (
    <>
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
      <NewsletterModal open={newsletterOpen} onClose={() => setNewsletterOpen(false)} />

      <header className="sticky top-0 z-50 border-b border-[#1e1e1e14] bg-[#f8f7f4]/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1166px] items-center justify-between gap-4 px-4 py-4 sm:px-8 sm:py-5">
          <Link href="/">
            <div className="flex min-w-0 cursor-pointer flex-col">
              <div className="[font-family:'Playfair_Display',Helvetica] text-[22px] font-bold leading-[22px] tracking-[3px] text-[#1e1e1e] sm:text-[26px] sm:leading-[26px] sm:tracking-[3.90px]">
                WishNest
              </div>
              <div className="hidden pt-0.5 [font-family:'Inter',Helvetica] text-[8px] font-normal leading-[11px] tracking-[1.40px] text-[#6b6b6b] sm:block sm:text-[9px] sm:leading-[12px] sm:tracking-[1.60px]">
                HOSPITALITY · ARCHITECTURE
                <br />
                SECOND HOME INTELLIGENCE
              </div>
            </div>
          </Link>

          <nav className="hidden items-center gap-5 lg:flex" aria-label="Primary">
            {navLinks.map((item) =>
              item.children ? (
                <div
                  key={item.label}
                  className="relative"
                  onMouseEnter={() => setIntelOpen(true)}
                  onMouseLeave={() => setIntelOpen(false)}
                >
                  <Link href={item.href}>
                    <span
                      className={`inline-flex cursor-pointer items-center gap-0.5 whitespace-nowrap [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.10px] transition-opacity hover:opacity-70 ${
                        location.startsWith("/intelligence")
                          ? "text-[#2e4a3f]"
                          : "text-[#1e1e1e]"
                      }`}
                    >
                      {item.label}
                      <ChevronDown className="h-3 w-3 opacity-50" />
                    </span>
                  </Link>
                  {intelOpen && (
                    <div className="absolute left-0 top-full z-50 min-w-[220px] border border-[#1e1e1e14] bg-[#f8f7f4] py-2 shadow-lg">
                      {item.children.map((c) => (
                        <Link key={c.href + c.label} href={c.href}>
                          <span
                            className={`block cursor-pointer px-4 py-2.5 [font-family:'Inter',Helvetica] text-[12px] transition hover:bg-[#2e4a3f]/8 ${
                              location === c.href
                                ? "text-[#2e4a3f]"
                                : "text-[#1e1e1e]"
                            }`}
                          >
                            {c.label}
                          </span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <Link key={item.label} href={item.href}>
                  <span
                    className={`cursor-pointer whitespace-nowrap [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.10px] transition-opacity hover:opacity-70 ${
                      isActive(item.href) ? "text-[#2e4a3f]" : "text-[#1e1e1e]"
                    }`}
                  >
                    {item.label}
                  </span>
                </Link>
              ),
            )}
          </nav>

          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Search"
              onClick={() => setSearchOpen(true)}
              className="rounded-full p-2 text-[#1e1e1e] hover:bg-[#1e1e1e0a]"
            >
              <Search className="h-4 w-4" />
            </button>
            <Button
              variant="outline"
              onClick={() => setNewsletterOpen(true)}
              className="hidden h-9 rounded-none border-[#1e1e1e] px-4 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1.2px] sm:inline-flex"
            >
              NEWSLETTER
            </Button>
            <button
              type="button"
              className="p-2 lg:hidden"
              aria-label="Menu"
              onClick={() => setMobileOpen((o) => !o)}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="border-t border-[#1e1e1e14] bg-[#f8f7f4] px-4 py-4 lg:hidden">
            <div className="flex flex-col gap-1">
              {navLinks.map((item) => (
                <div key={item.label}>
                  <Link href={item.href}>
                    <span
                      onClick={() => setMobileOpen(false)}
                      className="block cursor-pointer py-2.5 [font-family:'Inter',Helvetica] text-[13px] font-medium tracking-[1px] text-[#1e1e1e]"
                    >
                      {item.label}
                    </span>
                  </Link>
                  {item.children?.map((c) => (
                    <Link key={c.href + c.label} href={c.href}>
                      <span
                        onClick={() => setMobileOpen(false)}
                        className="block cursor-pointer py-2 pl-4 text-[12px] text-[#6b6b6b]"
                      >
                        {c.label}
                      </span>
                    </Link>
                  ))}
                </div>
              ))}
              <button
                type="button"
                onClick={() => {
                  setMobileOpen(false);
                  setNewsletterOpen(true);
                }}
                className="mt-2 py-2 text-left text-[12px] font-medium tracking-[1px] text-[#2e4a3f]"
              >
                NEWSLETTER
              </button>
            </div>
          </div>
        )}
      </header>
    </>
  );
};
