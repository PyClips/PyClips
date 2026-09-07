# Deploy pyclips.in (Railway)

Marketing site + accounts API. This repository **is** the deploy root (Dockerfile at repo root).

## 1. Railway

```powershell
railway login
railway init
railway up
```

Connect this GitHub repo in Railway with **root directory** `/` (default).

## 2. Environment variables

Copy `.env.example` → `.env` locally. In Railway → Variables, set at minimum:

| Variable | Value |
|----------|--------|
| `PYCLIPS_PUBLIC_URL` | `https://pyclips.in` |
| `PYCLIPS_DATA_DIR` | `/data` |
| `GOOGLE_CLIENT_ID` | from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | from Google Cloud Console |
| `RAZORPAY_KEY_ID` | Razorpay dashboard |
| `RAZORPAY_KEY_SECRET` | Razorpay dashboard |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay webhook |
| `RAZORPAY_PLAN_MONTHLY` / `YEARLY` | plan ids |

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
