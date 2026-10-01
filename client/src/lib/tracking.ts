/**
 * Analytics helpers — GA4, Meta Pixel, optional LinkedIn.
 * IDs from Vite env (set on Vercel):
 *   VITE_GA_MEASUREMENT_ID=G-XXXXXXXX
 *   VITE_META_PIXEL_ID=1234567890
 *   VITE_LINKEDIN_PARTNER_ID=xxxxxxx
 */

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
    fbq?: (...args: unknown[]) => void;
    lintrk?: ((...args: unknown[]) => void) & { q?: unknown[] };
  }
}

const GA_ID = (import.meta.env.VITE_GA_MEASUREMENT_ID || "").trim();
const META_ID = (import.meta.env.VITE_META_PIXEL_ID || "").trim();
const LI_ID = (import.meta.env.VITE_LINKEDIN_PARTNER_ID || "").trim();

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"] as const;

export type UtmParams = Partial<Record<(typeof UTM_KEYS)[number], string>>;

export function captureUtmFromUrl(search: string = window.location.search): UtmParams {
  const params = new URLSearchParams(search);
  const out: UtmParams = {};
  for (const k of UTM_KEYS) {
    const v = params.get(k);
    if (v) out[k] = v.slice(0, 128);
  }
  if (Object.keys(out).length) {
    try {
      sessionStorage.setItem("wishnest_utm", JSON.stringify(out));
    } catch {
      /* ignore */
    }
  }
  return out;
}

export function getStoredUtm(): UtmParams {
  try {
    const raw = sessionStorage.getItem("wishnest_utm");
    if (!raw) return {};
    return JSON.parse(raw) as UtmParams;
  } catch {
    return {};
  }
}

/** Channel for application source (URL ?source= or utm_source). */
export function resolveApplicationSource(): string {
  const params = new URLSearchParams(window.location.search);
  const explicit = params.get("source") || params.get("ref");
  if (explicit) return explicit.slice(0, 64);
  const utm = { ...getStoredUtm(), ...captureUtmFromUrl() };
  if (utm.utm_source) return String(utm.utm_source).slice(0, 64);
  return "website";
}

export function initTracking(): void {
  captureUtmFromUrl();

  if (GA_ID && !document.getElementById("ga4-script")) {
    const s = document.createElement("script");
    s.id = "ga4-script";
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag(...args: unknown[]) {
      window.dataLayer?.push(args);
    };
    window.gtag("js", new Date());
    window.gtag("config", GA_ID, { send_page_view: false });
  }

  if (META_ID && !document.getElementById("meta-pixel")) {
    const s = document.createElement("script");
    s.id = "meta-pixel";
    s.innerHTML = `
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '${META_ID}');
`;
    document.head.appendChild(s);
  }

  if (LI_ID && !document.getElementById("li-insight")) {
    const s = document.createElement("script");
    s.id = "li-insight";
    s.innerHTML = `
_linkedin_partner_id = "${LI_ID}";
window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
window._linkedin_data_partner_ids.push(_linkedin_partner_id);
(function(l) {
  if (!l){window.lintrk = function(a,b){window.lintrk.q.push([a,b])};
  window.lintrk.q=[]}
  var s = document.getElementsByTagName("script")[0];
  var b = document.createElement("script");
  b.type = "text/javascript";b.async = true;
  b.src = "https://snap.licdn.com/li.lms-analytics/insight.min.js";
  s.parentNode.insertBefore(b, s);
})(window.lintrk);
`;
    document.head.appendChild(s);
  }
}

export function trackPageView(path: string): void {
  if (GA_ID && window.gtag) {
    window.gtag("event", "page_view", {
      page_path: path,
      page_location: window.location.href,
      page_title: document.title,
    });
  }
  if (META_ID && window.fbq) {
    window.fbq("track", "PageView");
  }
}

export function trackEvent(
  name: string,
  params?: Record<string, string | number | boolean | undefined>,
): void {
  if (GA_ID && window.gtag) {
    window.gtag("event", name, params || {});
  }
  if (META_ID && window.fbq) {
    // Map common conversions
    if (name === "generate_lead" || name === "submit_application") {
      window.fbq("track", "Lead", params);
    } else {
      window.fbq("trackCustom", name, params);
    }
  }
  if (LI_ID && window.lintrk && (name === "generate_lead" || name === "submit_application")) {
    window.lintrk("track", { conversion_id: LI_ID });
  }
}
