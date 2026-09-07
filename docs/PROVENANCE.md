# PyClips provenance

This file records how PyClips was developed and how original work is separated
from third-party components. It is a development and licensing record, not a
warranty that PyClips has no functional overlap with other video-clipping tools.

## Product and this repository

PyClips is a video-clipping product:

- **Website** — this GitHub repository: marketing, accounts, Google sign-in, and
  Razorpay Premium for [pyclips.in](https://pyclips.in).
- **Windows desktop editor** — independently implemented in a separate product
  tree. It is not published in this repository.

Official GitHub: [github.com/PyClips/PyClips](https://github.com/PyClips/PyClips).

## Original PyClips work

Original PyClips source, UI, branding, configuration, and package metadata in
this repository are proprietary. See [LICENSE](../LICENSE).

That includes website Python code under `app/` and the React UI under `web/`.

Third-party libraries, fonts loaded from CDNs, and commercial APIs are **not**
original PyClips code. They remain under their upstream licenses or vendor
terms. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and
[NOTICE](../NOTICE).

The desktop editor's original code is likewise proprietary PyClips work. Its
third-party stack (FFmpeg, faster-whisper, models, caption fonts, and so on) is
inventoried in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) so this public
repository has a complete product record.

## Independent implementation

PyClips was independently implemented as its own product.

During development, a packaged third-party video-clipping application
(Clipshlip) was inspected only to compare high-level architecture and
functionality — for example, that a clip workflow may include ingest,
transcription, clip selection, caption burn-in, and export. That inspection was
not used as a source of implementation material.

PyClips does not copy, translate, refactor, rename, adapt, or reproduce source
code, UI code, assets, branding, configuration, package metadata, or other
implementation material from Clipshlip, UniSin, AutoClips, or other proprietary
products.

## Expected similarities

PyClips uses widely available technologies (Python, FastAPI, React, FFmpeg,
faster-whisper, and similar) and implements a general video-clipping workflow.
Functional or architectural similarities to other clip tools that use the same
class of stack are expected. Those similarities do not mean source code was
reused.

This document does **not** claim that PyClips is guaranteed to contain no
similar code to any other program, and it does not claim that no similar product
exists.

## Related documents

- [LICENSE](../LICENSE) — PyClips original-code license
- [NOTICE](../NOTICE) — short attribution list
- [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) — verified third-party inventory
