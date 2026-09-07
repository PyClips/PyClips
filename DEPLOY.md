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

In Google Cloud Console, add to your OAuth web client:

- **Origins:** `https://pyclips.in`, `https://www.pyclips.in`
- **Redirect URIs:** `https://pyclips.in/api/auth/google/callback`

## 5. Verify

```powershell
curl https://pyclips.in/health
```

Should return JSON with `"status":"ok"`.
