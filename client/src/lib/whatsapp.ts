/** WhatsApp helpers — wa.me links (no Cloud API required). */

export function digitsOnlyPhone(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const d = raw.replace(/\D/g, "");
  return d.length >= 8 ? d : null;
}

export function waMeUrl(phoneDigits: string, text?: string): string {
  const base = `https://wa.me/${phoneDigits}`;
  if (!text) return base;
  return `${base}?text=${encodeURIComponent(text)}`;
}

/** Business number from Vite env (E.164 digits, country code, no +). */
export function businessWhatsAppNumber(): string | null {
  const n = (import.meta.env.VITE_WHATSAPP_BUSINESS_NUMBER || "").replace(/\D/g, "");
  return n.length >= 8 ? n : null;
}

export function publicWhatsAppCta(
  message = "Hello WishNest — I would like to get my hospitality project reviewed.",
): string | null {
  const n = businessWhatsAppNumber();
  if (!n) return null;
  return waMeUrl(n, message);
}
