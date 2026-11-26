/**
 * WishNest × ArrowX — contextual AI advertising landing page.
 * Framework: relevance → capability → conversation. No forms-first.
 */
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearch } from "wouter";
import {
  ArrowRight,
  Calendar,
  MessageCircle,
  Mic,
  Phone,
  Sparkles,
  X,
  ChevronLeft,
  ChevronRight,
  Send,
  Volume2,
} from "lucide-react";
import { usePageMeta } from "@/hooks/usePageMeta";
import { businessWhatsAppNumber, waMeUrl } from "@/lib/whatsapp";
import {
  AdvisoryCampaign,
  getCampaign,
  PresentationItem,
  ProjectItem,
} from "@/lib/advisoryCampaigns";
import {
  ProtectedPdfViewer,
  ProtectedVideoPlayer,
  ProtectedImageSetViewer,
} from "@/components/ProtectedMedia";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
function apiUrl(path: string) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

const CALENDAR_URL =
  (import.meta.env.VITE_ADVISORY_CALENDAR_URL as string) ||
  "https://calendly.com/";

type ChatMsg = { role: "assistant" | "user"; text: string };

function statusLabel(s: ProjectItem["status"]) {
  if (s === "completed") return "Completed";
  if (s === "ongoing") return "Ongoing";
  return "Concept";
}

export function AdvisoryLandingPage(): JSX.Element {
  const params = useParams<{ topic?: string }>();
  const search = useSearch();
  const campaign = useMemo(() => getCampaign(params.topic), [params.topic]);

  usePageMeta({
    title: campaign.metaTitle,
    description: campaign.metaDescription,
    path: campaign.path,
  });

  // Attribution from URL
  useEffect(() => {
    try {
      const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
      const attr = {
        topic: campaign.topic,
        utm_source: q.get("utm_source") || "",
        utm_medium: q.get("utm_medium") || "",
        utm_campaign: q.get("utm_campaign") || "",
        path: campaign.path,
        at: new Date().toISOString(),
      };
      sessionStorage.setItem("wn_advisory_attr", JSON.stringify(attr));
    } catch {
      /* ignore */
    }
  }, [campaign, search]);

  const [aiOpen, setAiOpen] = useState(false);
  const [aiContext, setAiContext] = useState<string | null>(null);
  const [deck, setDeck] = useState<PresentationItem | null>(null);
  const [mediaPresentation, setMediaPresentation] = useState<PresentationItem | null>(null);
  const [slideIdx, setSlideIdx] = useState(0);
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [callbackOpen, setCallbackOpen] = useState(false);

  const openAi = (ctx?: string) => {
    setAiContext(ctx || null);
    setAiOpen(true);
  };

  const phoneDigits = businessWhatsAppNumber() || "919199440961";
  const waChat = waMeUrl(phoneDigits, campaign.whatsappPrefill);
  const waVoice = waMeUrl(
    phoneDigits,
    `${campaign.whatsappPrefill}\n\n(I will send a voice note about my project.)`,
  );

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e] antialiased">
      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-[#1e1e1a]/10 bg-[#f8f7f4]/90 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:h-16 sm:px-6">
          <div className="flex items-center gap-3 sm:gap-4">
            <Link href="/" className="font-serif text-[15px] tracking-tight text-[#1e1e1e] sm:text-base">
              WishNest
            </Link>
            <span className="hidden text-[#1e1e1a]/25 sm:inline">×</span>
            <span className="hidden font-serif text-[15px] tracking-tight text-[#2e4a3f] sm:inline">
              ArrowX
            </span>
          </div>
          <p className="hidden text-[11px] tracking-wide text-[#6b6b6b] md:block">
            Intelligence by WishNest · Architecture by ArrowX
          </p>
          <button
            type="button"
            onClick={() => openAi()}
            className="rounded-full border border-[#2e4a3f]/30 bg-[#2e4a3f] px-4 py-1.5 text-[12px] font-medium text-[#f8f7f4] transition hover:bg-[#243a32]"
          >
            Let&apos;s talk
          </button>
        </div>
      </header>

      <main>
        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className="mx-auto grid max-w-6xl gap-0 lg:grid-cols-2 lg:min-h-[70vh]">
          <div className="relative aspect-[4/3] overflow-hidden lg:aspect-auto lg:min-h-[70vh]">
            {campaign.heroVideo ? (
              <video
                src={campaign.heroVideo}
                className="h-full w-full object-cover"
                autoPlay
                muted
                loop
                playsInline
                controlsList="nodownload"
                poster={campaign.heroImage}
                onContextMenu={(e) => e.preventDefault()}
              />
            ) : (
              <img
                src={campaign.heroImage}
                alt=""
                className="h-full w-full object-cover"
                fetchPriority="high"
              />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/25 to-transparent lg:bg-gradient-to-r lg:from-transparent lg:to-black/10" />
          </div>
          <div className="flex flex-col justify-center px-5 py-10 sm:px-10 lg:px-14">
            <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.2em] text-[#2e4a3f]">
              WishNest × ArrowX
            </p>
            <h1 className="font-serif text-[2rem] leading-[1.15] tracking-tight text-[#1e1e1e] sm:text-4xl lg:text-[2.75rem]">
              {campaign.headline}
            </h1>
            <p className="mt-4 max-w-md text-[15px] leading-relaxed text-[#6b6b6b] sm:text-base">
              {campaign.support}
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={() => openAi()}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-[#2e4a3f] px-6 text-[13px] font-medium text-[#f8f7f4] transition hover:bg-[#243a32]"
              >
                Let&apos;s talk about your project
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => scrollTo("presentations")}
                className="inline-flex h-12 items-center justify-center rounded-full border border-[#1e1e1a]/20 px-6 text-[13px] font-medium text-[#1e1e1e] transition hover:border-[#2e4a3f]/40 hover:text-[#2e4a3f]"
              >
                Explore presentations &amp; works
              </button>
            </div>
          </div>
        </section>

        {/* ── Presentations ────────────────────────────────────── */}
        <section id="presentations" className="border-t border-[#1e1e1a]/08 bg-[#f4f1ea]">
          <div className="mx-auto max-w-6xl px-5 py-14 sm:px-6 sm:py-20">
            <h2 className="font-serif text-2xl tracking-tight text-[#1e1e1e] sm:text-3xl">
              Explore the possibilities.
            </h2>
            <p className="mt-2 max-w-lg text-[14px] text-[#6b6b6b]">
              A short selection relevant to this conversation — no registration required.
            </p>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {campaign.presentations.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    if (p.mediaType === "pdf" || p.mediaType === "video") {
                      setMediaPresentation(p);
                    } else {
                      setDeck(p);
                      setSlideIdx(0);
                    }
                  }}
                  className="group overflow-hidden rounded-2xl border border-[#1e1e1a]/10 bg-[#f8f7f4] text-left shadow-sm transition hover:border-[#2e4a3f]/25"
                >
                  <div className="aspect-[16/10] overflow-hidden">
                    <img
                      src={p.cover}
                      alt=""
                      className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                      loading="lazy"
                    />
                  </div>
                  <div className="p-5">
                    <h3 className="font-serif text-lg leading-snug text-[#1e1e1e]">{p.title}</h3>
                    <span className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-medium text-[#2e4a3f]">
                      {p.mediaType === "video"
                        ? "Watch film"
                        : p.mediaType === "pdf"
                          ? "View full presentation"
                          : "View presentation"}{" "}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* ── Selected works ───────────────────────────────────── */}
        <section id="works" className="border-t border-[#1e1e1a]/08">
          <div className="mx-auto max-w-6xl px-5 py-14 sm:px-6 sm:py-20">
            <h2 className="font-serif text-2xl tracking-tight text-[#1e1e1e] sm:text-3xl">
              Ideas translated into architecture.
            </h2>
            <p className="mt-2 max-w-lg text-[14px] text-[#6b6b6b]">
              Selected ArrowX work — relevance over volume.
            </p>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {campaign.projects.map((pr) => (
                <button
                  key={pr.id}
                  type="button"
                  onClick={() => setProject(pr)}
                  className="group overflow-hidden rounded-2xl border border-[#1e1e1a]/10 bg-white text-left transition hover:border-[#2e4a3f]/25"
                >
                  <div className="aspect-[4/3] overflow-hidden">
                    <img
                      src={pr.image}
                      alt=""
                      className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                      loading="lazy"
                    />
                  </div>
                  <div className="p-5">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-[#6b6b6b]">
                      <span>{pr.category}</span>
                      <span className="text-[#1e1e1a]/20">·</span>
                      <span>{statusLabel(pr.status)}</span>
                    </div>
                    <h3 className="mt-1.5 font-serif text-lg text-[#1e1e1e]">{pr.name}</h3>
                    {pr.location && (
                      <p className="mt-0.5 text-[12px] text-[#6b6b6b]">{pr.location}</p>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* ── Communication gateway ────────────────────────────── */}
        <section id="talk" className="border-t border-[#1e1e1a]/08 bg-[#1e1e1e] text-[#f8f7f4]">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-6 sm:py-24">
            <h2 className="font-serif text-3xl tracking-tight sm:text-4xl">
              Don&apos;t like filling forms?
            </h2>
            <p className="mt-2 font-serif text-2xl text-[#f8f7f4]/70 sm:text-3xl">
              Neither do we.
            </p>
            <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-[#f8f7f4]/55">
              You don&apos;t need to prepare a project brief, write a lengthy email or have all
              the answers. Simply tell us what you have in mind, in whichever way feels most
              comfortable.
            </p>

            {/* AI primary */}
            <div className="mt-12 overflow-hidden rounded-3xl border border-white/10 bg-white/[0.04] p-6 sm:p-10">
              <div className="flex flex-col gap-8 lg:flex-row lg:items-center">
                <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#2e4a3f] to-[#1a2e28] shadow-lg">
                  <Sparkles className="h-10 w-10 text-[#e8efe9]" />
                </div>
                <div className="flex-1">
                  <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[#9cb5a8]">
                    AI project assistant
                  </p>
                  <h3 className="mt-1 font-serif text-2xl sm:text-3xl">
                    Just tell her what you have in mind.
                  </h3>
                  <p className="mt-3 max-w-lg text-[14px] leading-relaxed text-[#f8f7f4]/55">
                    Talk to our AI assistant. She will ask a few relevant questions, understand
                    your requirements and prepare your project enquiry for you. No lengthy forms.
                  </p>
                  <div className="mt-6 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => openAi()}
                      className="inline-flex h-12 items-center gap-2 rounded-full bg-[#f8f7f4] px-6 text-[13px] font-medium text-[#1e1e1e] transition hover:bg-white"
                    >
                      <Mic className="h-4 w-4" />
                      Start talking
                    </button>
                    <button
                      type="button"
                      onClick={() => openAi()}
                      className="inline-flex h-12 items-center gap-2 rounded-full border border-white/20 px-6 text-[13px] font-medium text-[#f8f7f4] transition hover:border-white/40"
                    >
                      Prefer to type?
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Four channel cards */}
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <ChannelCard
                icon={<MessageCircle className="h-5 w-5" />}
                title="Prefer WhatsApp?"
                body="Message our team directly."
                cta="WhatsApp us"
                href={waChat}
              />
              <ChannelCard
                icon={<Volume2 className="h-5 w-5" />}
                title="Don't feel like typing?"
                body="Send a voice note in your own words."
                cta="Send a voice note"
                href={waVoice}
              />
              <ChannelCard
                icon={<Phone className="h-5 w-5" />}
                title="Prefer speaking to a person?"
                body="Request a callback from our team at your convenience."
                cta="Request human callback"
                onClick={() => setCallbackOpen(true)}
              />
              <ChannelCard
                icon={<Calendar className="h-5 w-5" />}
                title="Ready for a focused discussion?"
                body="Book a discovery call with a senior advisor."
                cta="Choose a convenient time"
                href={campaign.calendarUrl || CALENDAR_URL}
              />
            </div>

            <p className="mt-10 max-w-xl text-[12px] leading-relaxed text-[#f8f7f4]/40">
              Your ideas remain yours. We share your approved project brief with our advisory
              team only with your permission.{" "}
              <Link href="/privacy" className="underline hover:text-[#f8f7f4]/70">
                Privacy policy
              </Link>
            </p>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#1e1e1a]/10 bg-[#f8f7f4]">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-8 text-[12px] text-[#6b6b6b] sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>WishNest × ArrowX — Intelligence &amp; architecture for place-led projects.</p>
          <Link href="/" className="text-[#2e4a3f] hover:underline">
            wishnest.info
          </Link>
        </div>
      </footer>

      {/* Persistent bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-[#1e1e1a]/10 bg-[#f8f7f4]/95 px-3 py-2.5 backdrop-blur-md sm:bottom-4 sm:left-1/2 sm:right-auto sm:-translate-x-1/2 sm:rounded-full sm:border sm:px-2 sm:shadow-lg">
        <div className="mx-auto flex max-w-md items-center justify-center gap-1 sm:gap-0">
          <button
            type="button"
            onClick={() => openAi()}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-2.5 text-[12px] font-medium text-[#1e1e1e] hover:bg-[#2e4a3f]/10 sm:flex-none sm:px-4"
          >
            <Sparkles className="h-3.5 w-3.5 text-[#2e4a3f]" />
            Talk to AI
          </button>
          <a
            href={waChat}
            target="_blank"
            rel="noopener noreferrer"
            className="flex flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-2.5 text-[12px] font-medium text-[#1e1e1e] hover:bg-[#2e4a3f]/10 sm:flex-none sm:px-4"
          >
            <MessageCircle className="h-3.5 w-3.5 text-[#2e4a3f]" />
            WhatsApp
          </a>
          <button
            type="button"
            onClick={() => setCallbackOpen(true)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-2.5 text-[12px] font-medium text-[#1e1e1e] hover:bg-[#2e4a3f]/10 sm:flex-none sm:px-4"
          >
            <Phone className="h-3.5 w-3.5 text-[#2e4a3f]" />
            Request human callback
          </button>
        </div>
      </div>
      <div className="h-16 sm:h-8" />

      {/* Overlays */}
      {mediaPresentation?.mediaType === "pdf" && mediaPresentation.mediaSrc && (
        <ProtectedPdfViewer
          src={mediaPresentation.mediaSrc}
          title={mediaPresentation.title}
          onClose={() => setMediaPresentation(null)}
        />
      )}
      {mediaPresentation?.mediaType === "video" && mediaPresentation.mediaSrc && (
        <ProtectedVideoPlayer
          src={mediaPresentation.mediaSrc}
          title={mediaPresentation.title}
          onClose={() => setMediaPresentation(null)}
        />
      )}
      {deck && (
        <PresentationViewer
          deck={deck}
          index={slideIdx}
          onIndex={setSlideIdx}
          onClose={() => setDeck(null)}
          onDiscuss={() => {
            setDeck(null);
            openAi(`I was viewing the presentation “${deck.title}”.`);
          }}
        />
      )}
      {project && (
        <ProjectOverlay
          project={project}
          onClose={() => setProject(null)}
          onDiscuss={() => {
            setProject(null);
            openAi(
              `I was looking at the ArrowX project “${project.name}”. Could something like this work for my project?`,
            );
          }}
        />
      )}
      {aiOpen && (
        <AiAssistantPanel
          campaign={campaign}
          context={aiContext}
          onClose={() => setAiOpen(false)}
        />
      )}
      {callbackOpen && (
        <CallbackModal
          topic={campaign.topic}
          onClose={() => setCallbackOpen(false)}
        />
      )}
    </div>
  );
}

function ChannelCard({
  icon,
  title,
  body,
  cta,
  href,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  cta: string;
  href?: string;
  onClick?: () => void;
}) {
  const className =
    "flex flex-col rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-left transition hover:border-white/25 hover:bg-white/[0.05]";
  const inner = (
    <>
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-[#9cb5a8]">
        {icon}
      </div>
      <h4 className="font-serif text-lg leading-snug text-[#f8f7f4]">{title}</h4>
      <p className="mt-1.5 flex-1 text-[13px] leading-relaxed text-[#f8f7f4]/50">{body}</p>
      <span className="mt-4 inline-flex items-center gap-1 text-[12px] font-medium text-[#9cb5a8]">
        {cta} <ArrowRight className="h-3.5 w-3.5" />
      </span>
    </>
  );
  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
        {inner}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} className={className}>
      {inner}
    </button>
  );
}

function PresentationViewer({
  deck,
  index,
  onIndex,
  onClose,
  onDiscuss,
}: {
  deck: PresentationItem;
  index: number;
  onIndex: (n: number) => void;
  onClose: () => void;
  onDiscuss: () => void;
}) {
  const slide = deck.slides[index];
  const last = index >= deck.slides.length - 1;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-3 sm:p-6">
      <div className="relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-[#f8f7f4] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#1e1e1a]/10 px-4 py-3">
          <p className="truncate text-[13px] font-medium text-[#1e1e1e]">{deck.title}</p>
          <button type="button" onClick={onClose} className="rounded-full p-1.5 hover:bg-black/5">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {slide.image && (
            <div className="aspect-[16/9] bg-[#1e1e1e]">
              <img src={slide.image} alt="" className="h-full w-full object-cover" />
            </div>
          )}
          <div className="p-6 sm:p-8">
            <h3 className="font-serif text-2xl text-[#1e1e1e]">{slide.title}</h3>
            <p className="mt-3 text-[15px] leading-relaxed text-[#6b6b6b]">{slide.body}</p>
            {last && (
              <button
                type="button"
                onClick={onDiscuss}
                className="mt-8 inline-flex items-center gap-2 rounded-full bg-[#2e4a3f] px-5 py-2.5 text-[13px] font-medium text-white hover:bg-[#243a32]"
              >
                Discuss how this could apply to your project
                <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between border-t border-[#1e1e1a]/10 px-4 py-3">
          <button
            type="button"
            disabled={index === 0}
            onClick={() => onIndex(index - 1)}
            className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-[12px] disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" /> Previous
          </button>
          <span className="text-[11px] text-[#6b6b6b]">
            {index + 1} / {deck.slides.length}
          </span>
          <button
            type="button"
            disabled={last}
            onClick={() => onIndex(index + 1)}
            className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-[12px] disabled:opacity-30"
          >
            Next <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function ProjectOverlay({
  project,
  onClose,
  onDiscuss,
}: {
  project: ProjectItem;
  onClose: () => void;
  onDiscuss: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-3 sm:p-6">
      <div className="relative max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-[#f8f7f4] shadow-2xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 z-10 rounded-full bg-black/40 p-1.5 text-white hover:bg-black/60"
        >
          <X className="h-5 w-5" />
        </button>
        <div className="aspect-[16/10]">
          <img src={project.image} alt="" className="h-full w-full object-cover" />
        </div>
        <div className="p-6 sm:p-8">
          <p className="text-[11px] uppercase tracking-wider text-[#6b6b6b]">
            {project.category} · {statusLabel(project.status)}
            {project.location ? ` · ${project.location}` : ""}
          </p>
          <h3 className="mt-1 font-serif text-2xl text-[#1e1e1e]">{project.name}</h3>
          <p className="mt-3 text-[15px] leading-relaxed text-[#6b6b6b]">{project.description}</p>
          <button
            type="button"
            onClick={onDiscuss}
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#2e4a3f] px-5 py-2.5 text-[13px] font-medium text-white hover:bg-[#243a32]"
          >
            Could something like this work for my project?
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function AiAssistantPanel({
  campaign,
  context,
  onClose,
}: {
  campaign: AdvisoryCampaign;
  context: string | null;
  onClose: () => void;
}) {
  const opening = context
    ? `I see you've been exploring something specific. ${context} Would you like to discuss how a similar approach could apply to your own project?`
    : campaign.aiOpening;

  const [msgs, setMsgs] = useState<ChatMsg[]>([{ role: "assistant", text: opening }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [summaryMode, setSummaryMode] = useState(false);
  const [summary, setSummary] = useState("");
  const [contact, setContact] = useState({ name: "", phone: "", email: "" });
  const [submitted, setSubmitted] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, summaryMode]);

  const replyFor = (userText: string, history: ChatMsg[]): string => {
    const t = userText.toLowerCase();
    const turns = history.filter((m) => m.role === "user").length;
    if (turns <= 1) {
      return "Thank you for sharing that. Where is the site or property located, roughly — city, region, or landscape setting?";
    }
    if (turns === 2) {
      return "Understood. What feels most important to you right now — exploring options, design direction, or connecting with the team for a focused discussion?";
    }
    if (turns >= 3 || /\b(call|team|human|person|book|schedule)\b/.test(t)) {
      return "I've noted what you've shared. I can prepare a short summary for our advisory team so you don't have to explain everything again — would you like that? Reply yes, or tell me anything else to add.";
    }
    return "That helps. Is there anything else about the project you'd like us to know before we connect you with the team?";
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    const next = [...msgs, { role: "user" as const, text: trimmed }];
    setMsgs(next);
    setInput("");
    setBusy(true);
    await new Promise((r) => setTimeout(r, 500));
    const lower = trimmed.toLowerCase();
    if (
      /\b(yes|haan|हां|ok|okay|summary|share)\b/.test(lower) &&
      next.filter((m) => m.role === "user").length >= 2
    ) {
      const userBits = next.filter((m) => m.role === "user").map((m) => m.text);
      const draft = [
        `Topic: ${campaign.headline}`,
        `Campaign: ${campaign.topic}`,
        ...userBits.map((b, i) => `${i + 1}. ${b}`),
      ].join("\n");
      setSummary(draft);
      setSummaryMode(true);
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          text: "I've prepared a short summary of what you've told me. You can review and edit it, then share contact details so our team can reach you.",
        },
      ]);
    } else {
      setMsgs((m) => [...m, { role: "assistant", text: replyFor(trimmed, next) }]);
    }
    setBusy(false);
  };

  const submitEnquiry = async (e: FormEvent) => {
    e.preventDefault();
    const phone = contact.phone.replace(/\D/g, "");
    if (phone.length < 10) return;
    setBusy(true);
    try {
      let attr = {};
      try {
        attr = JSON.parse(sessionStorage.getItem("wn_advisory_attr") || "{}");
      } catch {
        /* */
      }
      await fetch(apiUrl("/api/public/request-call"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: contact.phone,
          name: contact.name || undefined,
          email: contact.email || undefined,
          note: `[Advisory ${campaign.topic}] ${summary}\n\nAttr: ${JSON.stringify(attr)}`,
        }),
      });
      setSubmitted(true);
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          text: "Thank you. Your summary has been shared with our team. They will be in touch using the details you provided.",
        },
      ]);
    } catch {
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          text: "Something went wrong submitting the enquiry. You can WhatsApp us directly from the page, or try again.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
      <button type="button" className="absolute inset-0 bg-black/50" onClick={onClose} aria-label="Close" />
      <div className="relative flex h-[min(92vh,720px)] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[#f8f7f4] shadow-2xl sm:rounded-3xl">
        <div className="flex items-center justify-between border-b border-[#1e1e1a]/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#2e4a3f] text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-[#1e1e1e]">Mira · AI assistant</p>
              <p className="text-[11px] text-[#6b6b6b]">WishNest × ArrowX · not a human</p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-1.5 hover:bg-black/5">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {msgs.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed ${
                  m.role === "user"
                    ? "bg-[#2e4a3f] text-white"
                    : "bg-white text-[#1e1e1e] shadow-sm ring-1 ring-black/5"
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
          {pasteOpen && (
            <div className="rounded-2xl border border-[#1e1e1a]/10 bg-white p-3">
              <p className="text-[12px] font-medium text-[#1e1e1e]">
                Already discussed your project with ChatGPT?
              </p>
              <textarea
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                rows={3}
                placeholder="Paste a short summary — optional"
                className="mt-2 w-full rounded-xl border border-[#1e1e1a]/15 bg-[#f8f7f4] px-3 py-2 text-[13px] outline-none focus:border-[#2e4a3f]"
              />
              <button
                type="button"
                className="mt-2 text-[12px] font-medium text-[#2e4a3f]"
                onClick={() => {
                  if (pasteText.trim()) {
                    void send(`ChatGPT summary: ${pasteText.trim()}`);
                    setPasteOpen(false);
                    setPasteText("");
                  }
                }}
              >
                Continue from this
              </button>
            </div>
          )}
          {summaryMode && !submitted && (
            <form onSubmit={submitEnquiry} className="space-y-3 rounded-2xl border border-[#2e4a3f]/20 bg-white p-4">
              <label className="block text-[11px] font-medium uppercase tracking-wide text-[#6b6b6b]">
                Summary (editable)
              </label>
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={5}
                className="w-full rounded-xl border border-[#1e1e1a]/15 px-3 py-2 text-[13px] outline-none focus:border-[#2e4a3f]"
              />
              <input
                placeholder="Name (optional)"
                value={contact.name}
                onChange={(e) => setContact((c) => ({ ...c, name: e.target.value }))}
                className="w-full rounded-xl border border-[#1e1e1a]/15 px-3 py-2 text-[13px] outline-none focus:border-[#2e4a3f]"
              />
              <input
                required
                placeholder="Phone"
                value={contact.phone}
                onChange={(e) => setContact((c) => ({ ...c, phone: e.target.value }))}
                className="w-full rounded-xl border border-[#1e1e1a]/15 px-3 py-2 text-[13px] outline-none focus:border-[#2e4a3f]"
              />
              <input
                placeholder="Email (optional)"
                value={contact.email}
                onChange={(e) => setContact((c) => ({ ...c, email: e.target.value }))}
                className="w-full rounded-xl border border-[#1e1e1a]/15 px-3 py-2 text-[13px] outline-none focus:border-[#2e4a3f]"
              />
              <button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-full bg-[#2e4a3f] text-[13px] font-medium text-white hover:bg-[#243a32] disabled:opacity-60"
              >
                Share with the team
              </button>
            </form>
          )}
          <div ref={bottomRef} />
        </div>

        {!summaryMode && (
          <div className="border-t border-[#1e1e1a]/10 p-3">
            <button
              type="button"
              onClick={() => setPasteOpen((v) => !v)}
              className="mb-2 text-[11px] text-[#6b6b6b] underline"
            >
              Already discussed with ChatGPT?
            </button>
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send(input);
                  }
                }}
                placeholder="Type in English, Hindi, or Hinglish…"
                className="flex-1 rounded-full border border-[#1e1e1a]/15 bg-white px-4 py-2.5 text-[14px] outline-none focus:border-[#2e4a3f]"
              />
              <button
                type="button"
                disabled={busy || !input.trim()}
                onClick={() => void send(input)}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-[#2e4a3f] text-white disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-center text-[10px] text-[#6b6b6b]">
              Voice: use your device keyboard mic, or WhatsApp voice note on the page.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function CallbackModal({ topic, onClose }: { topic: string; onClose: () => void }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [when, setWhen] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await fetch(apiUrl("/api/public/request-call"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone,
          name: name || undefined,
          note: `[Advisory callback · ${topic}] Preferred time: ${when || "anytime"}`,
        }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail || "Could not record callback");
      }
      setDone(true);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-[#f8f7f4] p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-xl text-[#1e1e1e]">Request human callback</h3>
          <button type="button" onClick={onClose} className="rounded-full p-1 hover:bg-black/5">
            <X className="h-5 w-5" />
          </button>
        </div>
        {done ? (
          <p className="mt-4 text-[14px] text-[#2e4a3f]">
            Request recorded. Our team will call you — no need to wait on this page.
          </p>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-3">
            <input
              placeholder="Name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl border border-[#1e1e1a]/15 px-3 py-2.5 text-[14px] outline-none focus:border-[#2e4a3f]"
            />
            <input
              required
              placeholder="Phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full rounded-xl border border-[#1e1e1a]/15 px-3 py-2.5 text-[14px] outline-none focus:border-[#2e4a3f]"
            />
            <input
              placeholder="Preferred time (optional)"
              value={when}
              onChange={(e) => setWhen(e.target.value)}
              className="w-full rounded-xl border border-[#1e1e1a]/15 px-3 py-2.5 text-[14px] outline-none focus:border-[#2e4a3f]"
            />
            {err && <p className="text-[12px] text-red-600">{err}</p>}
            <button
              type="submit"
              disabled={busy}
              className="h-11 w-full rounded-full bg-[#2e4a3f] text-[13px] font-medium text-white hover:bg-[#243a32] disabled:opacity-60"
            >
              {busy ? "Sending…" : "Request human callback"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default AdvisoryLandingPage;
