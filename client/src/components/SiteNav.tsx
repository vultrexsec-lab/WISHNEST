import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { Menu, X, Search, ChevronDown } from "lucide-react";
import { SearchModal } from "@/components/SearchModal";
import { NewsletterModal } from "@/components/NewsletterModal";

/** Magazine reading vs commercial/service paths — client audit P2 */
const readLinks = [
  { label: "Reviews", href: "/reviews" },
  { label: "Destinations", href: "/destinations" },
  { label: "Best Of", href: "/best-of" },
  {
    label: "Intelligence",
    href: "/intelligence",
    children: [
      { label: "Overview", href: "/intelligence" },
      { label: "Hospitality Intelligence", href: "/intelligence/hospitality" },
      { label: "Villa Intelligence", href: "/intelligence/villa" },
    ],
  },
  { label: "Contributors", href: "/contributors" },
];

const workLinks = [
  { label: "Reimagined™", href: "/reimagined" },
  { label: "Get Reviewed", href: "/get-reviewed" },
];

export const SiteNav = () => {
  const [location] = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [newsletterOpen, setNewsletterOpen] = useState(false);
  const [intelOpen, setIntelOpen] = useState(false);

  const isActive = (href: string) =>
    location === href || (href !== "/" && location.startsWith(href + "/"));

  const linkClass = (href: string) =>
    `whitespace-nowrap [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.10px] transition-opacity hover:opacity-70 ${
      isActive(href) ? "text-[#2e4a3f]" : "text-[#1e1e1e]"
    }`;

  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:text-[#2e4a3f] focus:outline focus:outline-2"
      >
        Skip to content
      </a>
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

          <nav
            className="hidden items-center gap-5 lg:flex xl:gap-6"
            aria-label="Primary"
          >
            <span className="hidden text-[9px] font-medium tracking-[1.5px] text-[#6b6b6b] xl:inline">
              READ
            </span>
            {readLinks.map((item) =>
              item.children ? (
                <div
                  key={item.label}
                  className="relative"
                  onMouseEnter={() => setIntelOpen(true)}
                  onMouseLeave={() => setIntelOpen(false)}
                >
                  <button
                    type="button"
                    className={`inline-flex items-center gap-1 ${linkClass(item.href)}`}
                    aria-expanded={intelOpen}
                    aria-haspopup="true"
                    onClick={() => setIntelOpen((o) => !o)}
                  >
                    {item.label}
                    <ChevronDown className="h-3 w-3" aria-hidden />
                  </button>
                  {intelOpen && (
                    <div
                      className="absolute left-0 top-full z-50 min-w-[220px] border border-[#1e1e1e14] bg-[#f8f7f4] py-2 shadow-lg"
                      role="menu"
                    >
                      {item.children.map((c) => (
                        <Link key={c.href} href={c.href}>
                          <span
                            role="menuitem"
                            className="block cursor-pointer px-4 py-2 text-[12px] text-[#1e1e1e] hover:bg-[#1e1e1e08]"
                            onClick={() => setIntelOpen(false)}
                          >
                            {c.label}
                          </span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <Link key={item.href} href={item.href}>
                  <span className={`cursor-pointer ${linkClass(item.href)}`}>{item.label}</span>
                </Link>
              ),
            )}
            <span className="mx-1 h-3 w-px bg-[#1e1e1e20]" aria-hidden />
            <span className="hidden text-[9px] font-medium tracking-[1.5px] text-[#6b6b6b] xl:inline">
              WORK WITH US
            </span>
            {workLinks.map((item) => (
              <Link key={item.href} href={item.href}>
                <span className={`cursor-pointer ${linkClass(item.href)}`}>{item.label}</span>
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2 sm:gap-3">
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="flex h-9 w-9 items-center justify-center text-[#1e1e1e] transition-opacity hover:opacity-70"
              aria-label="Search"
            >
              <Search className="h-4 w-4" />
            </button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setNewsletterOpen(true)}
              className="hidden h-auto rounded-none border-[0.8px] border-[#2e4a3f] bg-transparent px-4 py-2 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.32px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white sm:inline-flex"
            >
              Newsletter
            </Button>
            <button
              type="button"
              className="flex h-9 w-9 items-center justify-center text-[#1e1e1e] lg:hidden"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen((o) => !o)}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div
            className="border-t border-[#1e1e1e14] bg-[#f8f7f4] px-4 py-4 lg:hidden"
            role="dialog"
            aria-label="Mobile navigation"
          >
            <p className="mb-2 text-[9px] font-medium tracking-[2px] text-[#6b6b6b]">READ</p>
            {readLinks.map((item) => (
              <div key={item.label}>
                <Link href={item.href}>
                  <span
                    onClick={() => setMobileOpen(false)}
                    className="block cursor-pointer border-b border-[#1e1e1e0a] py-3.5 text-[13px] font-medium tracking-[1.1px] text-[#1e1e1e]"
                  >
                    {item.label}
                  </span>
                </Link>
                {item.children?.map((c) => (
                  <Link key={c.href} href={c.href}>
                    <span
                      onClick={() => setMobileOpen(false)}
                      className="block cursor-pointer border-b border-[#1e1e1e0a] py-2.5 pl-4 text-[12px] text-[#6b6b6b]"
                    >
                      {c.label}
                    </span>
                  </Link>
                ))}
              </div>
            ))}
            <p className="mb-2 mt-4 text-[9px] font-medium tracking-[2px] text-[#6b6b6b]">
              WORK WITH US
            </p>
            {workLinks.map((item) => (
              <Link key={item.href} href={item.href}>
                <span
                  onClick={() => setMobileOpen(false)}
                  className="block cursor-pointer border-b border-[#1e1e1e0a] py-3.5 text-[13px] font-medium tracking-[1.1px] text-[#1e1e1e]"
                >
                  {item.label}
                </span>
              </Link>
            ))}
            <button
              type="button"
              onClick={() => {
                setMobileOpen(false);
                setNewsletterOpen(true);
              }}
              className="mt-4 w-full border border-[#2e4a3f] py-3 text-[11px] tracking-[1.3px] text-[#2e4a3f]"
            >
              Newsletter
            </button>
          </div>
        )}
      </header>
    </>
  );
};
