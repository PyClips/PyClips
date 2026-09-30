/** Real installer / Store URLs only. Leave empty until they exist — never invent links. */
export const DOWNLOAD_URL = "";
export const MICROSOFT_STORE_URL = "https://apps.microsoft.com/detail/9PBTL4Z79XTQ";

/** Creator-link checkout on systeme.io (₹99 monthly, ₹599 lifetime unlocked build). */
export const SYSTEME_MONTHLY_URL = "https://checkout.pyclips.in/monthly";
export const SYSTEME_LIFETIME_URL = "https://checkout.pyclips.in/lifetime";

/** systeme.io's affiliate redirect drops ?sa= before pyclips.in, and its sale webhook has no affiliate
 * field, so creators share pyclips.in/?sa=CODE and the code rides along to checkout in the URL. */
const AFFILIATE_KEY = "pyclips_sa";

export function rememberAffiliate() {
  try {
    const sa = (new URLSearchParams(window.location.search).get("sa") || "").trim();
    if (/^[A-Za-z0-9_-]{2,80}$/.test(sa)) window.localStorage.setItem(AFFILIATE_KEY, sa);
  } catch {
    /* private mode: no storage */
  }
}

export function checkoutUrl(base) {
  let sa = "";
  try {
    sa = window.localStorage.getItem(AFFILIATE_KEY) || "";
  } catch {
    sa = "";
  }
  return sa ? `${base}?sa=${encodeURIComponent(sa)}` : base;
}

/** Temporarily hidden on the landing page; flip back to true to show again. */
export const SHOW_HERO_DOWNLOAD = false;
export const SHOW_HERO_STORE = false;
export const SHOW_PRICING_PANEL = false;
export const SHOW_DOWNLOAD_SECTION = false;
export const SHOW_FINAL_CTA = false;
export const SHOW_ACCOUNT_BUTTON = false;

export const SITE_URL = "https://pyclips.in";

export const SOCIALS = [
  { label: "X", href: "https://x.com/Py_Clips" },
  { label: "Discord", href: "https://discord.gg/bnDaDK3FQ" },
  { label: "GitHub", href: "https://github.com/PyClips" },
];
