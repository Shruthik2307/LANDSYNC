  # 🛰️ LAND SYNC - Frontend

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

  ## 🚀 Deployment (one URL — frontend + backend together)

  The whole app ships as a **single Render service**: Docker builds the Vite
  frontend, and FastAPI serves both the SPA and every `/api/*` route from one
  origin. No separate frontend host, no CORS, no local processes.

  [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Shruthik2307/LANDSYNC)

  1. Click the button → confirm → Render builds (`render.yaml` → service
     `landsync-sih26013`, first build ≈ 10–15 min for the GIS stack)
  2. When live, your app is at `https://landsync-sih26013.onrender.com` —
     open it: Backend: Connected, 25 parcels, full reconciliation UI
  3. Share that one URL with the team. Done.

  Notes:
  - Free plan: the service sleeps after ~15 min idle; the first visit then
    takes ~50s to wake (Render cold start). Paid plan is always-on.
  - Local development is still the classic two-process flow:
    `npm run dev` + `cd backend && python main.py`.

  ## 🧪 Testing & Quality Assurance

  We maintain a strict quality gate. Run the following commands to verify the build:

  - Unit Tests: npm run test
  - E2E Tests: npm run test:e2e
  - Coverage Report: Check the /coverage directory after running tests.

  ## 📄 License

  This project is licensed under the MIT License - see the LICENSE (LICENSE) file for details.
