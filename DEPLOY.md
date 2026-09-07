# Deploy pyclips.in (Railway)

Marketing site + accounts API. This repository **is** the deploy root (Dockerfile at repo root).

## 1. Railway (GitHub deploy)

Repo: [github.com/PyClips/PyClips](https://github.com/PyClips/PyClips) — this folder **is** the repo root.

```powershell
railway login
cd website   # if you cloned locally; repo root on GitHub is already the website
railway link # pick project "pyclips", service "pyclips"
railway service source connect --repo PyClips/PyClips --branch main --service pyclips
```

Do **not** use `railway up` for production — that uploads from your machine. Pushes to `main` on GitHub trigger deploys automatically.

Install the [Railway GitHub App](https://github.com/apps/railway-app) on the `PyClips` org if prompted.

## 2. Environment variables

Copy `.env.example` → `.env` locally. In Railway → Variables, set:

| Variable | Value |
|----------|--------|
| `PYCLIPS_PUBLIC_URL` | `https://pyclips.in` |
| `PYCLIPS_DATA_DIR` | `/data` |
| `PYCLIPS_ADMIN_PASSWORD` | strong secret (coupon admin at `/admin`) |
| `GOOGLE_CLIENT_ID` | Google Cloud Console → OAuth web client |
| `GOOGLE_CLIENT_SECRET` | same client |
| `RAZORPAY_KEY_ID` | Razorpay dashboard |
| `RAZORPAY_KEY_SECRET` | Razorpay dashboard |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay webhook |
| `RAZORPAY_PLAN_MONTHLY` | INR monthly plan id (`plan_…`) |
| `RAZORPAY_PLAN_YEARLY` | INR yearly plan id |
| `RAZORPAY_PLAN_MONTHLY_USD` | USD monthly plan id (International) |
| `RAZORPAY_PLAN_YEARLY_USD` | USD yearly plan id |

Mount a **Volume** at `/data` so accounts and redeem codes survive redeploys.

## 3. Custom domain

Railway → Service → Settings → Domains → **Add custom domain** → `pyclips.in` and `www.pyclips.in`.

At your DNS provider (where you bought the domain):

| Type | Name | Value |
|------|------|--------|
| CNAME | `@` or `pyclips.in` | Railway target (shown in dashboard) |
| CNAME | `www` | same target |

Wait for SSL (usually a few minutes).

## 4. Google OAuth

Open [Google Cloud Console → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent).

### Fix “Error 403: org_internal”

That error means the app is set to **Internal** (Workspace-only). PyClips needs **External** so any Google user can sign in.

1. **OAuth consent screen** → **Edit app**
2. **User type** → **External** (not Internal). Save.
3. **Publishing status**
   - **Testing** — add every email that should sign in under **Test users** (e.g. `pyclips.in@gmail.com`), then Save.
   - **In production** — any Google account can sign in (Google may ask for verification if you request sensitive scopes; email/profile/openid are usually fine).

### OAuth client (Web application)

[Credentials](https://console.cloud.google.com/apis/credentials) → your **Web client** (same `GOOGLE_CLIENT_ID` as Railway):

| Field | Values |
|-------|--------|
| **Authorized JavaScript origins** | `https://pyclips.in` · `http://127.0.0.1:8001` |
| **Authorized redirect URIs** | `https://pyclips.in/api/auth/google/callback` · `http://127.0.0.1:8001/api/auth/google/callback` |

Scopes used by the site: `openid`, `email`, `profile`.

### Railway (already required)

| Variable | Value |
|----------|--------|
| `PYCLIPS_PUBLIC_URL` | `https://pyclips.in` (must match redirect URI host) |
| `GOOGLE_CLIENT_ID` | Web client id ending in `.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Web client secret |

After changing Google settings, wait ~1 minute and try **Sign in with Google** again in a private/incognito window.

## 5. Verify

```powershell
curl https://pyclips.in/health
```

Should return JSON with `"status":"ok"`.
