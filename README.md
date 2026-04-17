# FlowPass

> Skip the crowd. Arrive on time, leave on time.

FlowPass is a single-screen companion app that tells a stadium attendee exactly when to arrive and exactly when to leave — fixing the two worst moments of any live match: the ingress crush and the egress flood.

It does one job and nothing else. No tickets, no food ordering, no social features. Just: **when do I walk out the door, and which gate do I use?**

**Live demo:** https://flowpass-717111183395.asia-south1.run.app

## Architecture at a glance

The core engineering idea: **AI does the work at build time, rules do the work at runtime.**

- **Build time** — Gemini generates the venue graph, crowd-flow model, and reason templates once. The output is committed as static JSON.
- **Runtime** — A deterministic Python rules engine reads that JSON and makes recommendations. Zero LLM calls on the recommendation hot path.
- **Accessibility first** — step-free routing for wheelchair users and strollers is a first-class input to the engine, not an afterthought.

Result: the main recommendation endpoint runs in single-digit milliseconds, costs nothing per request, is fully testable, and works offline when the venue JSON is cached.

```
app/
├── main.py          # FastAPI setup, thin route handlers, lifespan loading
├── config.py        # Pydantic-typed settings
├── routes.py        # POST /api/recommendation
├── models/          # Domain + I/O schemas (Pydantic)
├── engine/          # Pure-function rules engine (no I/O)
│   ├── congestion.py
│   └── recommender.py
├── services/        # External adapters (Gemini, Weather, loaders)
│   ├── gemini.py
│   ├── weather.py
│   ├── venue_loader.py
│   └── reason_templates_loader.py
├── data/            # Committed JSON (regenerable via scripts/)
├── templates/       # Jinja2 HTML
└── static/          # CSS
scripts/
└── generate_reason_templates.py   # Build-time Gemini call
```

Dependency direction: **templates → routes → engine → models**. Services live at the edge and are injected. The engine never imports anything from `routes` or `services` except Pydantic models.

## Google Services

Three Google services do real work in FlowPass, each with a distinct purpose.

| Service | What it does | Why this one |
|---|---|---|
| **Gemini 2.5 Flash** (AI Studio) | Build-time: generates reason template JSON (`scripts/generate_reason_templates.py`). Output ships in the repo; runtime reads static JSON. | Free tier, fast for structured JSON generation. Build-time use means zero LLM calls per user request — orders of magnitude cheaper than calling Gemini live. |
| **Maps JavaScript API** (Maps Demo Key) | Renders an interactive map below the recommendation card showing the selected gate and the nearest transit stop, with a polyline between them. | The Demo Key is free with no billing required. Maps JS supports markers, styling, and polyline rendering — exactly what we need for visualizing the last walking leg. |
| **Weather API** (Maps Demo Key) | Server-side fetch of current conditions at venue coordinates. Feeds into the engine: rain expected → prefer covered gates, rain now → escalate exit urgency. | Also covered by the Maps Demo Key. Integrating weather turns recommendations from mechanical to genuinely useful — "leave now, rain starting" beats "leave in 15 min" every time. |
| **Cloud Run** (hosting) | Containerized deployment, scales to zero, public HTTPS. | Free tier covers hackathon usage. Dockerfile is committed. |

**What we deliberately rejected:**

- *Directions API / Routes*: not supported by the Maps Demo Key; a static polyline from venue coordinates is sufficient for the demo.
- *Cloud Text-to-Speech*: the browser's Web Speech API does the same job with zero API cost, zero latency, and respects OS voice preferences.
- *Firestore / Firebase*: no user data is stored server-side by design. All preferences live in form state only.

## Running locally

```bash
uv sync
cp .env.example .env   # then add GEMINI_API_KEY and MAPS_API_KEY
uv run fastapi dev app/main.py
```

Visit http://localhost:8000.

Regenerate reason templates (build-time Gemini call, output committed to repo):

```bash
uv run python scripts/generate_reason_templates.py
```

## Quality gates

All four run in CI on every push to `main`.

| Tool | Purpose | Command |
|---|---|---|
| ruff | Lint + format | `uv run ruff check .` |
| mypy | Strict static typing | `uv run mypy app` |
| pytest | Unit + integration tests with coverage | `uv run pytest` |
| pip-audit | Dependency CVE scan | `uv run pip-audit` |

## Security

FlowPass takes security seriously even at demo stage:

- **No PII server-side** — preferences live in form state only; no auth, no accounts, no database.
- **Pydantic everywhere** — every user input is validated at the model layer. Bad input returns 422, never a stack trace.
- **Security headers middleware** — every response sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and a strict Content-Security-Policy that allows only the third-party origins we use (Tailwind CDN, Maps JS, Weather API).
- **Secrets never committed** — `.env` is gitignored; `.env.example` documents the shape without values.
- **Graceful service degradation** — if the Weather API or Gemini fails, the app falls back to base recommendations rather than surfacing an error.

## Accessibility

- Step-free routing for wheelchair users, strollers, and mobility needs — gate selection differs by this flag
- Semantic HTML with `aria-live="polite"` on the recommendation card
- Keyboard navigation with visible focus rings (WCAG AA contrast)
- `prefers-reduced-motion` respected in custom CSS
- Web Speech API "Read aloud" button (zero API cost, no data leaves the browser)
- Larger tap targets on touch devices (minimum 48×48px)
- Skip link at top of page
- All interactive elements reachable via Tab in logical order

## Deployment

Deployed to Google Cloud Run from this repo's `Dockerfile`. Environment variables are set via Cloud Run config, never committed.

```bash
gcloud run deploy flowpass --source . --region asia-south1 \
    --allow-unauthenticated --port 8080 --memory 512Mi \
    --set-env-vars "ENVIRONMENT=production,GEMINI_API_KEY=...,MAPS_API_KEY=..."
```

## License

MIT — see LICENSE.