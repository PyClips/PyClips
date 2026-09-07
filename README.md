# PyClips Website

Marketing site, accounts, Google sign-in, and Razorpay Premium for [pyclips.in](https://pyclips.in).

The Windows desktop clip editor is **not** in this repository.

[![Website](https://img.shields.io/badge/website-pyclips.in-7C5CFF)](https://pyclips.in)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

## License

PyClips is **proprietary software**. All rights reserved — see [LICENSE](LICENSE).

Third-party libraries are listed in [NOTICE](NOTICE).

## Local run

```powershell
copy .env.example .env
cd web
npm install
npm run build
cd ..
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Open http://127.0.0.1:8001

## Deploy (pyclips.in)

See [DEPLOY.md](DEPLOY.md) — Railway Docker deploy + custom domain + env vars.
