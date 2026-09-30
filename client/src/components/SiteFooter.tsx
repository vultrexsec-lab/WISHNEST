import { Link } from "wouter";

/** Only routes that actually exist in the app */
const footerLinks = [
  { label: "Reviews", href: "/reviews" },
  { label: "Destinations", href: "/destinations" },
  { label: "Best Of", href: "/best-of" },
  { label: "Intelligence", href: "/intelligence" },
  { label: "Contributors", href: "/contributors" },
  { label: "Reimagined", href: "/reimagined" },
  { label: "Newsletter", href: "/#newsletter" },
];

const socialLinks = [
  { label: "LI", href: "#", title: "LinkedIn" },
  { label: "TW", href: "#", title: "X / Twitter" },
  { label: "IN", href: "#", title: "Instagram" },
  { label: "YO", href: "#", title: "YouTube" },
];

export const SiteFooter = () => {
  return (
    <footer className="bg-[#161614]">
      <div className="mx-auto w-full max-w-[1166px] px-4 py-10 sm:px-8 sm:py-12">
        {/* Brand + links in one responsive band */}
        <div className="flex flex-col gap-8 border-b border-white/[0.08] pb-8 lg:flex-row lg:items-start lg:justify-between lg:gap-12">
          <div className="shrink-0 lg:max-w-[220px]">
            <Link href="/">
              <div className="cursor-pointer [font-family:'Playfair_Display',Helvetica] text-xl font-bold tracking-[2.5px] text-white sm:text-2xl">
                WishNest
              </div>
            </Link>
            <p className="pt-1.5 [font-family:'Inter',Helvetica] text-[9px] tracking-[1.4px] text-white/35">
              HOSPITALITY · ARCHITECTURE · SECOND HOME INTELLIGENCE
            </p>
            <p className="pt-3 max-w-[240px] [font-family:'Inter',Helvetica] text-[12px] leading-relaxed text-white/40">
              Independent editorial for architects, developers, and discerning investors.
            </p>
            <div className="mt-4 flex gap-3">
              {socialLinks.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  title={s.title}
                  className="[font-family:'Inter',Helvetica] text-[11px] tracking-[1px] text-white/30 transition hover:text-white/70"
                >
                  {s.label}
                </a>
              ))}
            </div>
          </div>

          {/* Real site links — single flowing row on desktop, wrap on mobile */}
          <nav
            aria-label="Footer"
            className="flex flex-1 flex-wrap content-start gap-x-5 gap-y-2.5 sm:gap-x-7 lg:justify-end lg:pt-1"
          >
            {footerLinks.map((link) => (
              <Link key={link.href + link.label} href={link.href}>
                <a className="[font-family:'Inter',Helvetica] text-[13px] text-white/55 transition hover:text-white">
                  {link.label}
                </a>
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="[font-family:'Inter',Helvetica] text-[11px] text-white/30">
            © {new Date().getFullYear()} WishNest. All rights reserved. Independent editorial — no paid placements.
          </p>
          <Link href="/">
            <a className="[font-family:'Inter',Helvetica] text-[11px] text-white/30 transition hover:text-white/50">
              Home
            </a>
          </Link>
        </div>
      </div>
    </footer>
  );
};
