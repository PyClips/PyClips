const cred = { credentials: "include" };

function errDetail(data, fallback) {
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0] && d[0].msg) return d[0].msg;
  return fallback;
}

async function jget(path) {
  const r = await fetch(path, cred);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(errDetail(data, `${path} → ${r.status}`));
    err.status = r.status;
    throw err;
  }
  return data;
}

async function jpost(path, body) {
  const r = await fetch(path, {
    ...cred,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(errDetail(data, `${path} → ${r.status}`));
    err.status = r.status;
    throw err;
  }
  return data;
}

export const api = {
  me: () => jget("/api/auth/me"),
  providers: () => jget("/api/auth/providers"),
  login: (email, password, ticket) => jpost("/api/auth/login", { email, password, ticket: ticket || "" }),
  register: (email, password, username, ticket) =>
    jpost("/api/auth/register", { email, password, username: username || "", ticket: ticket || "" }),
  logout: () => jpost("/api/auth/logout", {}),
  subscription: () => jget("/api/account/subscription"),
  peek: (ticket) => jget(`/api/desktop/peek?ticket=${encodeURIComponent(ticket)}`),
  bind: (ticket) => jpost(`/api/desktop/bind?ticket=${encodeURIComponent(ticket)}`, {}),
  pricing: (currency) => jget(`/api/billing/pricing${currency ? `?currency=${encodeURIComponent(currency)}` : ""}`),
  subscribe: (plan, ticket, currency) => jpost("/api/billing/subscribe", { plan, ticket: ticket || "", currency: currency || "" }),
  verify: (payload) => jpost("/api/billing/verify", payload),
  redeem: (code) => jpost("/api/billing/redeem", { code }),
  adminLogin: (password) => jpost("/api/admin/login", { password }),
  adminLogout: () => jpost("/api/admin/logout", {}),
  adminCoupons: () => jget("/api/admin/coupons"),
  adminCreate: (months, max_people, code) => jpost("/api/admin/coupons", { months, max_people, code: code || "" }),
  adminDelete: (code) => jpost("/api/admin/coupons/delete", { code }),
  adminDownload: () => jget("/api/admin/download"),
  adminSetDownload: (url) => jpost("/api/admin/download", { url }),
  adminClearDownload: () => jpost("/api/admin/download/clear", {}),
  publicDownload: () => jget("/api/download"),
};

export function loadRazorpay() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.async = true;
    const timer = setTimeout(() => reject(new Error("Checkout didn't load. Please retry or try another browser.")), 15000);
    s.onload = () => {
      clearTimeout(timer);
      if (!window.Razorpay) reject(new Error("Checkout didn't load. Please retry or try another browser."));
      else resolve();
    };
    s.onerror = () => {
      clearTimeout(timer);
      reject(new Error("Checkout didn't load. Please retry or try another browser."));
    };
    document.head.appendChild(s);
  });
}
