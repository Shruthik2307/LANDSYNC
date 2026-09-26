  # 🛰️ LAND SYNC - Frontend
https://landsync-production.up.railway.app/
  License (LICENSE)
  Build Status ()
  Test Coverage ()

  LAND SYNC is a high-performance frontend application designed for synchronizing and visualizing geospatial satellite
  data. Built with a modern React ecosystem, it focuses on precision, scalability, and a seamless user experience for
  handling complex land-data parcels.

  ## 🚀 Key Features

  - Interactive Mapping: Integrated mapping components for visualizing land parcels and satellite imagery.
  - API-First Architecture: Fully typed API integration based on OpenAPI 3.0 specifications.
  - Satellite Data Handling: Specialized utilities for processing and rendering satellite-derived geospatial assets.
  - Robust Validation: Schema-based data validation using Zod to ensure data integrity.
  - Comprehensive Testing: End-to-end (E2E) tests with Playwright and unit testing with Vitest for maximum reliability.

  ## 🛠️ Tech Stack

  - Core: React (https://reactjs.org/) + Vite (https://vitejs.dev/)
  - Styling: Tailwind CSS (https://tailwindcss.com/) + PostCSS (https://postcss.org/)
  - State & Validation: Zod (https://zod.dev/)
  - Testing: Vitest (https://vitest.dev/) (Unit) & Playwright (https://playwright.dev/) (E2E)
  - API Documentation: OpenAPI/Swagger (https://swagger.io/)
  - Fonts: Space Grotesk (via Fontshare)

  ## 📂 Project Structure

  ├── contract/           # API Specifications (OpenAPI) and Mock Data
  ├── public/             # Static assets, satellite SVGs, and custom fonts
  ├── server/             # Local mock server for development and testing
  ├── src/                # Application source code
  │   ├── components/     # Atomic design components (UI, Layout, Map, Screens)
  │   ├── api.js          # API service layer
  │   └── validation.js   # Zod schemas for data validation
  ├── tests/              # Test suite (Unit, E2E, and Fixtures)
  └── coverage/           # Test coverage reports

  ## ⚙️ Getting Started

  ### Prerequisites

  - Node.js (Latest LTS recommended)
  - npm or yarn
  - Python 3.11+ (backend; see backend/requirements.txt)

  > **Backend note:** the FastAPI server starts with zero configuration — it
  > defaults to a local SQLite database (`sqlite:///./landsync.db`). For
  > production, set `DATABASE_URL` to a PostGIS connection string (see
  > `backend/.env.example` and `.env.example`).

  ### Installation

  1. Clone the repository

     git clone https://github.com/your-username/land-sync-frontend.git
     cd land-sync-frontend

  2. Install dependencies

     npm install

  3. Environment Setup

     cp .env.example .env
     # Update .env with your API endpoints

  4. Run the Mock Server (Optional)

     node server/mock-server.mjs

  5. Launch Development Server

     npm run dev

  ## 🧪 Testing & Quality Assurance

  We maintain a strict quality gate. Run the following commands to verify the build:

  - Unit Tests: npm run test
  - E2E Tests: npm run test:e2e
  - Coverage Report: Check the /coverage directory after running tests.

  ## 🚀 Deployment — ONE authoritative production architecture

  Production is a **single Railway service** (`landsync-sih26013`). The Docker
  build compiles the Vite frontend, and FastAPI serves **both the SPA and every
  `/api/*` route from one URL**:

  > **https://landsync-sih26013-production.up.railway.app**

  - No CORS, no proxy rewrites, no second URL, no `VITE_API_BASE_URL` needed.
  - Deploy from the repo checkout: `cd <repo> && railway up` (Railway builds
    the Dockerfile cloud-side). Railway is linked to this project.

  ### Branch → production workflow (keep it this way)

  ```
  main  ──railway up──▶  Railway (landsync-sih26013)  ──▶  production
  ```

  - Production deploys **only** from `main`.
  - Feature branches are for review/CI only — never `railway up` from a
    feature branch, and never give a branch its own backend. A per-branch
    deployment with its own API is how conflicting "versions" of LANDSYNC
    with different parcel data appear.
  - CI (`.github/workflows/ci.yml`) enforces deployment hygiene and parcel
    data integrity on every push/PR to `main`.

  ### Obsolete deployments — manual decommission required

  These belong to teammates' personal accounts and can only be removed by
  their owners (do not share these URLs; they serve outdated data):

  | URL | Owner action |
  |---|---|
  | `https://landsync-cmcg.onrender.com` | Render dashboard → delete the `landsync-cmcg` service |
  | `https://landsync-sih.vercel.app` | Vercel dashboard → delete the project (it also proxies to the stale Render backend) |

  **Do not reintroduce split deployments.** A previous Vercel static deploy
  (`landsync-sih.vercel.app`) proxied `/api/*` to a *different, outdated*
  backend (`landsync-cmcg.onrender.com`), which served stale flattened parcel
  data. That configuration has been removed from the repository:
  `vercel.json` is deleted on purpose. If a Vercel deployment reappears, it
  must point at the canonical Railway URL — or better, not exist at all.

  ### Canonical data source

  One source of truth: `data/sample/cadastral.geojson` +
  `data/sample/municipal.geojson`, reconciled by `engine/` and cached by
  `backend/services/landsync_service.py`. `public/cadastral.geojson` (the
  Quick-Load sample button) and `src/data/*.geojson` are byte-for-byte
  copies of the same dataset and must be kept in sync or removed.

  ### ML confidence model — deliberately excluded

  The shipped `backend/models/conflict_detector.pkl` is degenerate (trained on
  a single-class sample: every parcel labeled "conflict"), so it predicts a
  constant and is **excluded from scoring**
  (`backend/services/landsync_service.py` logs this once at startup). The
  engine's rule-based confidence is authoritative. To safely re-enable ML:

  1. Produce genuine multi-class labels (conflict vs no-conflict) from
     adjudicated ground truth — not from the model's own input flags.
  2. Retrain with `backend/train_model.py` and verify on held-out data that
     predictions **vary** across parcels (a constant predictor must fail CI).
  3. Add a startup sanity check: if the model returns identical output for
     distinct inputs, refuse to load it.
  4. Re-introduce it as a *refinement* (never override) of the engine score,
     e.g. `0.7 * engine + 0.3 * ml`, with the blend logged.

  ## 📄 License

  This project is licensed under the MIT License - see the LICENSE (LICENSE) file for details.
