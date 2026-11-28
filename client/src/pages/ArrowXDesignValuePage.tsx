/**
 * Arrow X — Architecture That Creates Value
 * Faithful port of the client handoff landing (standalone HTML).
 * Route: /advisory/design-value
 */
import { useEffect, useMemo, useState, FormEvent } from "react";
import { Link } from "wouter";

const WA_DIGITS =
  (typeof import.meta !== "undefined" &&
    (import.meta.env.VITE_WHATSAPP_BUSINESS_NUMBER as string)?.replace(/\D/g, "")) ||
  "9199440961";

const ALLOWED_UTM = ["utm_source", "utm_medium", "utm_campaign", "utm_content"] as const;

function useAttribution() {
  return useMemo(() => {
    if (typeof window === "undefined") return {} as Record<string, string>;
    const params = new URLSearchParams(window.location.search);
    const out: Record<string, string> = {};
    for (const k of ALLOWED_UTM) {
      const v = (params.get(k) || "").replace(/[^a-zA-Z0-9_.-]/g, "").slice(0, 80);
      if (v) out[k] = v;
    }
    return out;
  }, []);
}

function track(event: string, placement: string, attribution: Record<string, string>) {
  if (typeof window === "undefined") return;
  const w = window as Window & { dataLayer?: Record<string, unknown>[] };
  w.dataLayer = w.dataLayer || [];
  w.dataLayer.push({ event, placement, ...attribution });
}

function buildMessage(
  project: string | undefined,
  details: string[],
  attribution: Record<string, string>,
) {
  return [
    "Hi Arrow X, I would like to discuss professional architectural or development consultancy.",
    project ? `Project: ${project}` : "",
    ...details,
    attribution.utm_source ? `Source: ${attribution.utm_source}` : "",
    attribution.utm_campaign ? `Campaign: ${attribution.utm_campaign}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

function waUrl(msg: string) {
  return `https://wa.me/${WA_DIGITS}?text=${encodeURIComponent(msg)}`;
}

const configured = /^[1-9]\d{7,14}$/.test(WA_DIGITS);

export default function ArrowXDesignValuePage() {
  const attribution = useAttribution();
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [location, setLocation] = useState("");
  const [stage, setStage] = useState("");
  const [budget, setBudget] = useState("");

  useEffect(() => {
    document.title = "Arrow X | Architecture That Creates Value";
  }, []);

  const openWa = (placement: string, project?: string, details: string[] = []) => {
    if (!configured) {
      setStatus("WhatsApp contact is not configured yet. Please check back later.");
      document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    track("whatsapp_click", placement, attribution);
    window.location.assign(waUrl(buildMessage(project, details, attribution)));
  };

  const onForm = (e: FormEvent) => {
    e.preventDefault();
    if (!configured) {
      setStatus("WhatsApp contact is not configured yet. Please check back later.");
      return;
    }
    const details = [
      location.trim() ? `Location: ${location.trim()}` : "",
      stage.trim() ? `Stage: ${stage.trim()}` : "",
      budget.trim() ? `Budget: ${budget.trim()}` : "",
    ].filter(Boolean);
    track("whatsapp_click", "optional_enquiry", attribution);
    window.location.assign(waUrl(buildMessage(type.trim() || undefined, details, attribution)));
  };

  return (
    <div className="ax-root">
      <style>{AX_CSS}</style>
      <a className="ax-skip" href="#main">
        Skip to content
      </a>
      <header className="ax-dark">
        <div className="ax-wrap ax-nav">
          <a className="ax-brand" href="#main" aria-label="Arrow X home">
            ARROW X
          </a>
          <button type="button" className="ax-btn" onClick={() => openWa("header")}>
            Discuss your project
          </button>
        </div>
      </header>

      <main id="main">
        <section className="ax-hero ax-dark">
          <div className="ax-wrap">
            <p className="ax-eyebrow">Architecture that creates value</p>
            <h1>Can your architect save you more than their fee?</h1>
            <p>
              Intelligent architecture for homes, second homes, resorts and developments. We explore
              ways to reduce avoidable construction costs while creating distinctive, lasting value.
            </p>
            <div className="ax-actions">
              <button type="button" className="ax-btn" onClick={() => openWa("hero")}>
                Discuss your project on WhatsApp
              </button>
              <a className="ax-btn ax-secondary" href="#services">
                Explore our expertise
              </a>
            </div>
            <p className="ax-small ax-muted">
              Professional architectural consultancy. Savings depend on site conditions, scope and
              engineering.
            </p>
            <p className="ax-region ax-eyebrow">Uttarakhand · Himachal Pradesh · Maharashtra</p>
          </div>
        </section>

        <section className="ax-section" id="services">
          <div className="ax-wrap">
            <div className="ax-intro">
              <p className="ax-eyebrow">What are you planning?</p>
              <h2>From a private home to an entire destination.</h2>
              <p>
                Start with the right architectural advice, whether you already have a brief or are
                still exploring possibilities.
              </p>
            </div>
            <div className="ax-grid">
              <ServiceTile
                n="01"
                title="Private homes & residences"
                body="Bespoke homes, bungalows and villas designed around your lifestyle, site and budget."
                cta="Discuss your home →"
                onClick={() => openWa("private-home", "Private home")}
              />
              <ServiceTile
                n="02"
                title="Second homes & farmhouses"
                body="Considering buying a second home? Explore the alternative of creating your own, from site assessment to architectural design."
                cta="Explore your second home →"
                onClick={() => openWa("second-home", "Second home")}
              />
              <ServiceTile
                n="03"
                title="Hotels & resorts"
                body="Hospitality architecture, guest experience, master planning and operating-model considerations."
                cta="Discuss your resort →"
                onClick={() => openWa("hospitality", "Hotel or resort")}
              />
              <ServiceTile
                n="04"
                title="Hill architecture"
                body="Terrain-responsive design, natural contours, access, infrastructure and construction economics."
                cta="Discuss your hill site →"
                onClick={() => openWa("hill", "Hill architecture")}
              />
              <ServiceTile
                n="05"
                title="Land & master planning"
                body="Explore development alternatives, site potential and appropriate architectural strategies."
                cta="Explore your land →"
                onClick={() => openWa("land", "Land development")}
              />
              <ServiceTile
                n="06"
                title="Renovation & design review"
                body="Rethink existing properties or review a proposed design before committing to construction."
                cta="Request a review →"
                onClick={() => openWa("review", "Design review or renovation")}
              />
            </div>
          </div>
        </section>

        <section className="ax-section ax-hill" id="hill">
          <div className="ax-wrap ax-split">
            <div>
              <p className="ax-eyebrow">Arrow X · Hill Intelligence</p>
              <h2>We understand the hills. We design with them.</h2>
              <p>Don&apos;t make the mountain fit the building. Explore how the building can fit the mountain.</p>
              <p>
                We consider excavation, retaining structures, foundations, access roads, drainage,
                material logistics, views and landscape together, from the earliest design stages.
              </p>
              <p className="ax-small ax-muted">
                Slope stability, seismic safety and structural integrity are non-negotiable.
                Site-specific engineering and approvals are essential.
              </p>
              <button
                type="button"
                className="ax-btn"
                onClick={() => openWa("hill-intelligence", "Hill architecture")}
              >
                Discuss your site
              </button>
            </div>
            <div>
              <HillDiagram />
              <p className="ax-small ax-muted">
                Conceptual illustration only; not an engineered section or a quantified savings
                comparison.
              </p>
            </div>
          </div>
        </section>

        <section className="ax-section ax-dark" id="strategy">
          <div className="ax-wrap">
            <p className="ax-eyebrow">Arrow X × WishNest</p>
            <h2>
              You own the land.
              <br />
              We help you discover what it could become.
            </h2>
            <p className="ax-intro">
              A boutique resort? A luxury retreat? A second-home destination? Or something entirely
              different? The opportunity lies in developing the right proposition, not simply
              developing the land.
            </p>
            <div className="ax-steps">
              <article>
                <h3 className="ax-accent">WHAT</h3>
                <p>Land potential, development alternatives and hospitality concepts.</p>
              </article>
              <article>
                <h3 className="ax-accent">WHY</h3>
                <p>WishNest customer intelligence, commissioned research and concept validation.</p>
              </article>
              <article>
                <h3 className="ax-accent">HOW</h3>
                <p>
                  Arrow X architecture, master planning, development strategy and potential operator
                  or investment partnerships.
                </p>
              </article>
            </div>
            <p className="ax-small ax-muted">
              Partnerships and brand collaborations are subject to suitability, due diligence and
              agreement.
            </p>
            <div className="ax-actions">
              <button
                type="button"
                className="ax-btn"
                onClick={() => openWa("strategy", "Land and development strategy")}
              >
                Explore your development opportunity
              </button>
              <a className="ax-btn ax-secondary" href="https://www.wishnest.info/">
                Explore WishNest
              </a>
            </div>
          </div>
        </section>

        <section className="ax-section">
          <div className="ax-wrap">
            <p className="ax-eyebrow">Before you build</p>
            <h2>Frequently asked questions</h2>
            <Faq
              q="Do you work outside hill locations?"
              a="Yes. Our intended service regions are the whole of Uttarakhand, Himachal Pradesh and Maharashtra, including urban and relatively flat sites. Project acceptance depends on scope and availability."
            />
            <Faq
              q="Can I consult you before buying land for a second home?"
              a="Yes. We can discuss a professional site assessment and architectural options before you commit to a property. Legal title, permissions and technical investigations require appropriate specialists."
            />
            <Faq
              q="Are your architectural services free?"
              a="No. Our proposition is that intelligent design may reduce avoidable project expenditure and create value that offsets professional fees. Savings are not guaranteed. Fees are agreed according to scope."
            />
            <Faq
              q="Can you help with an existing hotel or resort?"
              a="Yes. We can explore architectural transformation, repositioning, hospitality models and potential operator collaborations."
            />
            <Faq
              q="What happens after I contact you?"
              a="We discuss your project, location, stage and requirements, then propose an appropriate professional scope and fee if there is a fit."
            />
          </div>
        </section>

        <section className="ax-section ax-contact" id="contact">
          <div className="ax-wrap ax-split">
            <div>
              <p className="ax-eyebrow">Start a conversation</p>
              <h2>Let&apos;s explore what you can create.</h2>
              <p>Tell us about your home, second home, resort or land. No compulsory registration.</p>
              <button type="button" className="ax-btn" onClick={() => openWa("contact")}>
                Open WhatsApp
              </button>
              <p className="ax-small ax-muted" style={{ marginTop: 15 }}>
                You can also prepare a more detailed message using the optional fields alongside.
                Your message is only sent when you choose to send it in WhatsApp.
              </p>
            </div>
            <form className="ax-form" onSubmit={onForm}>
              <h3>Prepare your project enquiry</h3>
              <div className="ax-field">
                <label htmlFor="ax-type">Project type</label>
                <select id="ax-type" value={type} onChange={(e) => setType(e.target.value)}>
                  <option value="">Select if known</option>
                  <option>Private home</option>
                  <option>Second home or farmhouse</option>
                  <option>Hotel or resort</option>
                  <option>Land development</option>
                  <option>Design review or renovation</option>
                  <option>Other</option>
                </select>
              </div>
              <div className="ax-field">
                <label htmlFor="ax-location">Project location</label>
                <input
                  id="ax-location"
                  maxLength={120}
                  placeholder="Town, district or state"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </div>
              <div className="ax-field">
                <label htmlFor="ax-stage">Project stage</label>
                <select id="ax-stage" value={stage} onChange={(e) => setStage(e.target.value)}>
                  <option value="">Select if known</option>
                  <option>Exploring land or second homes</option>
                  <option>Already own land</option>
                  <option>Ready to appoint an architect</option>
                  <option>Existing property or design</option>
                </select>
              </div>
              <div className="ax-field">
                <label htmlFor="ax-budget">Indicative construction budget (optional)</label>
                <select id="ax-budget" value={budget} onChange={(e) => setBudget(e.target.value)}>
                  <option value="">Not decided / prefer to discuss</option>
                  <option>Below ₹50 lakh</option>
                  <option>₹50 lakh–₹1 crore</option>
                  <option>₹1–5 crore</option>
                  <option>Above ₹5 crore</option>
                </select>
              </div>
              <button className="ax-btn" type="submit">
                Continue to WhatsApp
              </button>
              <p className="ax-small ax-muted" style={{ marginTop: 12 }}>
                These fields are not submitted to a server by this page.
              </p>
              {status && (
                <p className="ax-status" role="status">
                  {status}
                </p>
              )}
            </form>
          </div>
        </section>
      </main>

      <footer className="ax-dark">
        <div className="ax-wrap">
          <p className="ax-brand">ARROW X</p>
          <p>Architecture that creates value. · From What to How.</p>
          <p>Uttarakhand · Himachal Pradesh · Maharashtra</p>
          <a href="https://www.wishnest.info/">WishNest</a>
          <Link href="/advisory/design-value/privacy">Privacy notice</Link>
          <p className="ax-small ax-muted" style={{ marginTop: 15 }}>
            © {new Date().getFullYear()} Arrow X. All rights reserved.
          </p>
        </div>
      </footer>

      <div className="ax-sticky">
        <button type="button" className="ax-btn" onClick={() => openWa("sticky")}>
          Discuss your project on WhatsApp
        </button>
      </div>
    </div>
  );
}

export function ArrowXDesignValuePrivacyPage() {
  useEffect(() => {
    document.title = "Privacy notice | Arrow X";
  }, []);
  return (
    <div style={{ maxWidth: 740, margin: "50px auto", padding: "0 24px", font: "17px/1.7 system-ui", color: "#203029" }}>
      <Link href="/advisory/design-value" style={{ color: "#216c49" }}>
        ← Arrow X
      </Link>
      <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400 }}>Privacy notice</h1>
      <p>
        This landing page prepares an optional enquiry message on your device. It does not submit the
        form fields to a server. If you continue to WhatsApp, your message is transferred to WhatsApp
        and is sent to Arrow X only when you choose to send it.
      </p>
      <p>
        Arrow X may use information you voluntarily share to respond to your enquiry, assess project
        suitability and discuss professional services. Campaign attribution may be included in your
        message.
      </p>
      <p>
        WhatsApp and the hosting provider may process information under their own policies. For the
        wider WishNest publication privacy practices, see the{" "}
        <a href="/policy" style={{ color: "#216c49" }}>
          WishNest policy
        </a>{" "}
        where applicable.
      </p>
    </div>
  );
}

function ServiceTile({
  n,
  title,
  body,
  cta,
  onClick,
}: {
  n: string;
  title: string;
  body: string;
  cta: string;
  onClick: () => void;
}) {
  return (
    <article className="ax-tile">
      <span className="ax-number">{n}</span>
      <h3>{title}</h3>
      <p>{body}</p>
      <button type="button" className="ax-tile-link" onClick={onClick}>
        {cta}
      </button>
    </article>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <details>
      <summary>{q}</summary>
      <p>{a}</p>
    </details>
  );
}

function HillDiagram() {
  return (
    <svg
      className="ax-diagram"
      viewBox="0 0 560 360"
      role="img"
      aria-labelledby="diagram-title"
    >
      <title id="diagram-title">
        Conceptual comparison of a level platform and stepped buildings following a slope
      </title>
      <rect width="560" height="360" fill="#e7ece2" />
      <g fill="#203029" fontFamily="system-ui" fontSize="15" fontWeight="600">
        <text x="24" y="30">
          Design against the terrain
        </text>
        <text x="24" y="205">
          Design with the terrain
        </text>
      </g>
      <g stroke="#78927b" strokeWidth="3" fill="none" strokeDasharray="6 5">
        <path d="M25 65L535 155" />
        <path d="M25 240L535 330" />
      </g>
      <path d="M25 65L170 91V130H420V135L535 155V170H25Z" fill="#b3a58e" />
      <path d="M170 90V130H420V135" fill="none" stroke="#765e45" strokeWidth="5" />
      <rect x="215" y="75" width="150" height="55" fill="#29483a" />
      <path d="M25 240L535 330V345H25Z" fill="#9caf95" />
      <g fill="#29483a">
        <rect x="95" y="213" width="90" height="42" />
        <rect x="235" y="238" width="90" height="42" />
        <rect x="375" y="263" width="90" height="42" />
      </g>
      <path d="M0 180H560" stroke="#bac7b9" />
    </svg>
  );
}

const AX_CSS = `
.ax-root{--green:#172820;--gold:#d9c49d;--paper:#f7f5ef;--ink:#203029;--muted:#53635a;--line:#d9ddd5;margin:0;font:17px/1.65 system-ui,sans-serif;color:var(--ink);background:var(--paper);min-height:100vh}
.ax-root *{box-sizing:border-box}
.ax-root a{color:inherit}
.ax-root h1,.ax-root h2,.ax-root h3,.ax-root p{margin:0 0 1rem}
.ax-root h1,.ax-root h2{font-family:Georgia,serif;font-weight:400;line-height:1.12}
.ax-root h1{font-size:clamp(2.7rem,6vw,5rem);max-width:850px}
.ax-root h2{font-size:clamp(2rem,4vw,3.2rem)}
.ax-root h3{font-size:1.15rem;line-height:1.35}
.ax-wrap{max-width:1160px;margin:auto;padding:0 24px}
.ax-eyebrow{font-size:.75rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase}
.ax-brand{font-size:1.45rem;letter-spacing:.24em;font-weight:700;text-decoration:none}
.ax-nav{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-block:18px}
.ax-dark{background:var(--green);color:var(--paper)}
.ax-dark .ax-eyebrow,.ax-dark .ax-accent{color:var(--gold)}
.ax-hero{position:relative;isolation:isolate;padding:100px 0 90px;background:linear-gradient(90deg,#172820 5%,#172820ed 40%,#17282080)}
.ax-hero p{max-width:660px;font-size:1.15rem}
.ax-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:13px 20px;border-radius:5px;background:#216c49;color:white;text-decoration:none;font-weight:650;border:1px solid transparent;cursor:pointer;font-size:1rem;min-height:48px;font-family:inherit}
.ax-dark .ax-btn{background:var(--gold);color:var(--green)}
.ax-btn.ax-secondary{background:transparent;border-color:currentColor;color:inherit}
.ax-actions{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}
.ax-small{font-size:.86rem}
.ax-muted{color:var(--muted)}
.ax-dark .ax-muted{color:#d4ddd4}
.ax-region{border-top:1px solid #ffffff30;padding-top:20px;margin-top:40px}
.ax-section{padding:76px 0}
.ax-intro{max-width:780px}
.ax-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:30px}
.ax-tile{border:1px solid var(--line);padding:24px;background:#fffdf8;border-radius:5px}
.ax-tile p{color:var(--muted)}
.ax-tile-link{font-weight:650;background:none;border:0;padding:0;color:inherit;cursor:pointer;font:inherit;text-align:left}
.ax-tile-link:hover{text-decoration:underline}
.ax-number{font-size:.8rem;letter-spacing:.1em;color:#68796d}
.ax-split{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:center}
.ax-diagram{width:100%;height:auto;background:#e7ece2;border-radius:5px}
.ax-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:25px;margin:30px 0}
.ax-steps article{border-top:1px solid #ffffff55;padding-top:20px}
.ax-hill{background:#e8ede5}
.ax-root details{border-bottom:1px solid var(--line);padding:17px 0}
.ax-root summary{cursor:pointer;font-weight:650}
.ax-root details p{margin:12px 0 0}
.ax-contact{background:#e6ece2}
.ax-contact .ax-split{align-items:start}
.ax-root label{display:block;font-size:.9rem;font-weight:650;margin-bottom:5px}
.ax-root input,.ax-root select{width:100%;font:inherit;padding:11px;border:1px solid #a8b5aa;border-radius:4px;background:white;color:var(--ink)}
.ax-field{margin-bottom:14px}
.ax-form{background:white;padding:25px;border-radius:6px}
.ax-form .ax-btn{width:100%}
.ax-status{font-size:.85rem;color:#a32e20;margin-top:10px}
.ax-sticky{display:none}
.ax-root footer{padding:30px 0;font-size:.85rem}
.ax-root footer a{margin-right:14px}
.ax-root a:focus-visible,.ax-root button:focus-visible,.ax-root summary:focus-visible,.ax-root input:focus-visible,.ax-root select:focus-visible{outline:3px solid #b58935;outline-offset:3px}
.ax-skip{position:absolute;left:-9999px}
.ax-skip:focus{left:10px;top:10px;z-index:99;background:white;padding:10px}
@media(max-width:760px){
  .ax-grid,.ax-steps,.ax-split{grid-template-columns:1fr}
  .ax-split{gap:24px}
  .ax-section{padding:48px 0}
  .ax-hero{padding:65px 0}
  .ax-nav .ax-btn{display:none}
  .ax-sticky{display:block;position:fixed;bottom:0;left:0;right:0;z-index:10;background:var(--paper);padding:10px 16px calc(10px + env(safe-area-inset-bottom));box-shadow:0 -3px 15px #0002}
  .ax-sticky .ax-btn{width:100%}
  .ax-root{padding-bottom:85px}
  .ax-wrap{padding-inline:20px}
}
`;
