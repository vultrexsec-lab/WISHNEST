import { Link } from "wouter";

const footerColumns = [
  {
    title: "FOR READERS",
    links: [
      { label: "Latest Reviews", href: "/reviews" },
      { label: "Destinations", href: "/destinations" },
      { label: "Best Of", href: "/best-of" },
      { label: "Intelligence", href: "/intelligence" },
      { label: "Contributors", href: "/contributors" },
    ],
  },
  {
    title: "FOR DEVELOPERS",
    links: [
      { label: "Property Insights", href: "/intelligence" },
      { label: "Architecture Guides", href: "/intelligence" },
      { label: "Design Standards", href: "/reimagined" },
      { label: "Case Studies", href: "/reimagined" },
    ],
  },
  {
    title: "FOR OPERATORS",
    links: [
      { label: "Get Reviewed", href: "/reviews" },
      { label: "Hospitality Research", href: "/intelligence" },
      { label: "WishNest Pro", href: "/contributors" },
      { label: "Submit a Property", href: "/contributors" },
    ],
  },
  {
    title: "FOR INVESTORS",
    links: [
      { label: "Market Intelligence", href: "/intelligence" },
      { label: "Second Home Index", href: "/best-of" },
      { label: "Destination Reports", href: "/destinations" },
      { label: "Briefings", href: "/intelligence" },
    ],
  },
  {
    title: "ABOUT",
    links: [
      { label: "Our Mission", href: "/contributors" },
      { label: "Privacy Policy", href: "/contributors" },
      { label: "Terms of Use", href: "/contributors" },
      { label: "Contact", href: "/contributors" },
      { label: "Newsletter", href: "/#newsletter" },
    ],
  },
];

export const SiteFooter = () => {
  return (
    <footer className="bg-[#161614]">
      <div className="mx-auto w-full max-w-[1166px] px-4 py-12 sm:px-8 lg:py-20">
        <div className="border-b border-[#ffffff14] pb-16">
          <div className="grid gap-12 lg:grid-cols-[240px_minmax(0,1fr)]">
            <div>
              <Link href="/">
                <div className="cursor-pointer [font-family:'Playfair_Display',Helvetica] text-2xl font-bold leading-9 tracking-[3.36px] text-white">
                  WishNest
                </div>
              </Link>
              <div className="pt-2 [font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.62px] text-[#ffffff59]">
                HOSPITALITY · ARCHITECTURE
                <br />
                SECOND HOME INTELLIGENCE
              </div>
              <p className="w-[200px] pt-6 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22.8px] text-[#ffffff73]">
                Independent editorial trusted by architects, developers,
                hospitality professionals and discerning investors.
              </p>
              <div className="flex gap-5 pt-8">
                {["LI", "TW", "IN", "YO"].map((item) => (
                  <button
                    key={item}
                    className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1px] text-[#ffffff4c] transition-opacity hover:opacity-70"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid gap-10 sm:grid-cols-2 xl:grid-cols-3">
              {footerColumns.slice(0, 3).map((column) => (
                <div key={column.title}>
                  <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.98px] text-[#ffffff4c]">
                    {column.title}
                  </div>
                  <ul className="space-y-3 pt-5">
                    {column.links.map((link) => (
                      <li key={link.label}>
                        <Link href={link.href}>
                          <span className="cursor-pointer [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[19.5px] text-[#ffffff8c] transition-opacity hover:opacity-70">
                            {link.label}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-14 grid gap-10 sm:grid-cols-2 xl:grid-cols-3 xl:pl-[304px]">
            {footerColumns.slice(3).map((column) => (
              <div key={column.title}>
                <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.98px] text-[#ffffff4c]">
                  {column.title}
                </div>
                <ul className="space-y-3 pt-5">
                  {column.links.map((link) => (
                    <li key={link.label}>
                      <Link href={link.href}>
                        <span className="cursor-pointer [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[19.5px] text-[#ffffff8c] transition-opacity hover:opacity-70">
                          {link.label}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-col justify-between gap-6 pt-8 md:flex-row md:items-center">
          <div className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#ffffff40]">
            © 2025 WishNest. All rights reserved. Independent editorial — no
            paid placements.
          </div>
          <div className="flex flex-wrap gap-7">
            {["Privacy", "Terms", "Newsletter", "Sitemap"].map((item) => (
              <button
                key={item}
                className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#ffffff40] transition-opacity hover:opacity-70"
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
};
