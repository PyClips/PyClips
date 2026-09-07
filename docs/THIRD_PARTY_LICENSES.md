# Third-party licenses

PyClips original code is proprietary ([LICENSE](../LICENSE)). This file lists
third-party components actually used by the PyClips product, as determined from
package manifests, source imports, and upstream documentation.

This GitHub repository contains the **website**. Desktop-only components are
included so the public record covers the full product.

License names below are taken from installed package metadata, upstream
repositories, or Hugging Face model cards. Items that still need a human check
are marked **unverified**. This file does not reproduce full third-party license
texts; keep the upstream notices with any redistributed binaries, wheels, fonts,
or model files.

**Scope**

- **Desktop** — Windows editor (separate product tree)
- **Website** — this repository (pyclips.in)
- **Both** — used in both

A packaged Python runtime also contains additional *transitive* packages. When
shipping that runtime, include the `*.dist-info` / `licenses/` files from
`site-packages` rather than treating this list as a complete pip freeze.

---

## 1. Open-source Python libraries

Website `requirements.txt` declares FastAPI, Uvicorn, requests, and
python-multipart. Desktop `requirements.txt` also declares pydantic, yt-dlp,
faster-whisper, and indic-transliteration.

| Component | Upstream | License (source of claim) | Scope |
| --- | --- | --- | --- |
| FastAPI | https://github.com/fastapi/fastapi | MIT (installed METADATA) | Both |
| Starlette | https://github.com/encode/starlette | BSD-3-Clause (installed METADATA) | Both (FastAPI dependency; imported on website) |
| Uvicorn | https://github.com/encode/uvicorn | BSD-3-Clause (installed METADATA) | Both |
| Pydantic | https://github.com/pydantic/pydantic | MIT (installed METADATA) | Both (declared on desktop; imported on website) |
| python-multipart | https://github.com/Kludex/python-multipart | Apache License 2.0 (installed METADATA) | Both |
| requests | https://github.com/psf/requests | Apache License 2.0 (installed METADATA) | Both |
| yt-dlp | https://github.com/yt-dlp/yt-dlp | Unlicense (installed METADATA) | Desktop |
| faster-whisper | https://github.com/SYSTRAN/faster-whisper | MIT (project LICENSE; installed METADATA) | Desktop |
| CTranslate2 | https://github.com/OpenNMT/CTranslate2 | MIT (installed METADATA) | Desktop (faster-whisper backend; imported) |
| Hugging Face Hub | https://github.com/huggingface/huggingface_hub | Apache License 2.0 (installed METADATA) | Desktop (imported) |
| indic-transliteration | https://github.com/indic-transliteration/indic_transliteration_py | MIT (installed METADATA) | Desktop |
| tokenizers | https://github.com/huggingface/tokenizers | Apache Software License (installed METADATA classifier; License field empty) | Desktop (faster-whisper stack) |
| ONNX Runtime | https://github.com/microsoft/onnxruntime | MIT (installed METADATA) | Desktop (VAD; imported, not in desktop `requirements.txt`) |
| pywebview | https://github.com/r0x0r/pywebview | BSD-3-Clause (installed METADATA) | Desktop (window; imported, not in desktop `requirements.txt`) |
| pythonnet | https://github.com/pythonnet/pythonnet | MIT (installed METADATA `License-Expression`) | Desktop (window icon; imported, not in desktop `requirements.txt`) |
| PyAV (`av`) | https://github.com/PyAV-Org/PyAV | BSD-3-Clause (installed METADATA) | Desktop (faster-whisper stack) |

---

## 2. Open-source JavaScript libraries

From this repository's `web/package.json` (website) and the desktop `web/package.json`.

| Component | Upstream | License (source of claim) | Scope |
| --- | --- | --- | --- |
| React | https://github.com/facebook/react | MIT (project license; npm `license` field) | Both |
| react-dom | https://github.com/facebook/react | MIT (same project) | Both |
| Vite | https://github.com/vitejs/vite | MIT (project license; npm `license` field) | Both (build) |
| @vitejs/plugin-react | https://github.com/vitejs/vite-plugin-react | MIT (npm `license` field) | Both (build) |

Production UI bundles may include additional Vite/React transitive packages.
Their licenses are recorded in `package-lock.json` (`license` fields) and in
each package's published LICENSE file.

---

## 3. Third-party models (desktop)

PyClips does not author speech-model weights. Models are downloaded at runtime
into a local cache. They are not published in this GitHub repository.

| Model | Upstream | License (source of claim) | Notes |
| --- | --- | --- | --- |
| `Systran/faster-whisper-*` (tiny / base / small / medium / large-v3, size auto-picked) | https://huggingface.co/Systran — conversions of OpenAI Whisper | Hugging Face Hub lists these conversions as **MIT**. Original Whisper code/weights: MIT ([openai/whisper LICENSE](https://github.com/openai/whisper/blob/main/LICENSE)) | Default ASR path via faster-whisper |
| `Hub84/faster-whisper-hinglish-prime` | https://huggingface.co/Hub84/faster-whisper-hinglish-prime — CTranslate2 conversion of Oriserve `Whisper-Hindi2Hinglish-Prime` | Model card states **Apache 2.0**, inherited from https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Prime (`license: apache-2.0`) | Optional Hinglish ASR |

If a desktop release **redistributes** model files, include the corresponding
Hugging Face model-card license and any files required by that license.

---

## 4. Fonts and webfonts

This website loads Inter, JetBrains Mono, and Outfit from the Google Fonts CDN
(`web/index.html`).

Desktop caption fonts are fetched from GitHub (`google/fonts` or
`googlefonts/roboto-2`) into a local fonts directory. They are not original
PyClips typefaces. User-uploaded fonts stay on the user's machine.

| Family | Source used by PyClips | License (source of claim) | Scope |
| --- | --- | --- | --- |
| Roboto Regular / Bold | https://github.com/googlefonts/roboto-2 | Apache License 2.0 (upstream project) | Desktop |
| Luckiest Guy; Permanent Marker | `google/fonts` `apache/` tree | Apache License 2.0 (`LICENSE.txt` in that tree; verified for Luckiest Guy) | Desktop |
| Anton, Bebas Neue, Archivo Black, Poppins, Montserrat, Oswald, Teko, Changa, Bangers, Alfa Slab One, Russo One, Titan One, Paytone One, Lilita One, Passion One, Sigmar One, Bowlby One SC, Concert One, Bungee, Shrikhand, DM Serif Display, Noto Nastaliq Urdu, Noto Naskh Arabic, Noto Sans Arabic, Noto Sans Devanagari, Noto Serif Devanagari | `google/fonts` `ofl/` tree | SIL Open Font License 1.1 (`OFL.txt` in that tree; Anton `OFL.txt` verified as the pattern for `ofl/` families) | Desktop |
| Playfair Display | Expected desktop file `PlayfairDisplay-Regular.ttf`; upstream OFL at `google/fonts` `ofl/playfairdisplay/OFL.txt` | SIL Open Font License 1.1 (verified OFL.txt) | Desktop (when the file is present) |
| Caveat | Expected desktop file `Caveat-Variable.ttf`; upstream OFL at `google/fonts` `ofl/caveat/OFL.txt` | SIL Open Font License 1.1 (verified OFL.txt) | Desktop (when the file is present) |
| Inter / Inter V | Google Fonts CDN; OFL at `google/fonts` `ofl/inter/OFL.txt` | SIL Open Font License 1.1 (verified OFL.txt) | Both |
| JetBrains Mono | Google Fonts CDN; https://github.com/JetBrains/JetBrainsMono | SIL Open Font License 1.1 (verified OFL.txt) | Both |
| Outfit | Google Fonts CDN; OFL at `google/fonts` `ofl/outfit/OFL.txt` | SIL Open Font License 1.1 (verified OFL.txt) | Both |

When redistributing font files, include each family's `OFL.txt` or `LICENSE.txt`
from upstream. Some OFL families declare Reserved Font Names (for example
Playfair Display).

Komika Axis is not shipped with PyClips; a commercial license was not verified.

---

## 5. External binaries and runtimes (desktop unless noted)

| Component | Upstream | License (source of claim) | How PyClips uses it |
| --- | --- | --- | --- |
| FFmpeg | https://ffmpeg.org | **Unverified for the exact binary.** FFmpeg builds are typically LGPL 2.1+ or GPL depending on compile options. See https://ffmpeg.org/legal.html | Desktop invokes FFmpeg as an external program |
| CPython (when bundled in the desktop installer) | https://www.python.org | Python Software Foundation License (interpreter `LICENSE` in that runtime) | Packaged Windows runtime |
| SQLite | https://www.sqlite.org | Public domain (SQLite blessing; via Python stdlib) | Both (local databases) |
| Microsoft Edge WebView2 Runtime | https://developer.microsoft.com/microsoft-edge/webview2/ | Microsoft software license terms for WebView2 (**not** an OSI open-source license) | Desktop window |
| NVIDIA CUDA / cuDNN Python wheels (`nvidia-cublas-cu12`, `nvidia-cuda-nvrtc-cu12`, `nvidia-cuda-runtime-cu12`, `nvidia-cudnn-cu12`) | NVIDIA PyPI packages | `License-Expression: LicenseRef-NVIDIA-Proprietary` (installed wheel METADATA) | Optional desktop GPU pack; not in the small installer |

Include the FFmpeg build's own license files in any installer that copies
`ffmpeg.exe`. Include NVIDIA `License.txt` from those wheels if the GPU pack is
redistributed.

---

## 6. Commercial / API terms (not open-source licenses)

| Service | Terms | Scope |
| --- | --- | --- |
| Razorpay | https://razorpay.com/terms/ | Website billing |
| Google APIs / OAuth | https://developers.google.com/terms | Website sign-in |

---

## 7. Still requires manual verification

1. **Exact FFmpeg binary** shipped with a given desktop installer (LGPL vs GPL).
2. **tokenizers** — Apache classifier is present; confirm the published LICENSE
   file for the exact wheel version on each desktop release.
3. **NVIDIA wheel `License.txt`** — proprietary; confirm redistribution rules
   for the GPU pack.
4. **WebView2** — include Microsoft's terms when redistributing the runtime or
   bootstrapper.
5. **Desktop extra font files on disk** — confirm they match the upstream
   families above before shipping.
6. **Default music / mask files** on the desktop — do not ship unverified media.
7. **Full pip/npm transitive closure** in a frozen release — copy license files
   from the bundled runtime rather than relying only on this summary.
