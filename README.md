# 28 Superhuman UI

A full-stack visual implementation of the 28 card game with:
- FastAPI backend (game engine + bot decisioning)
- React + Vite frontend (table UI, bidding/play panels, animations)
- WebSocket-driven live game state updates

This project is designed for desktop/laptop gameplay and includes:
- start screen
- mobile redirect screen
- configurable bot search depth via `.env` and `k_policy`

## What The System Does

At runtime:
1. Frontend creates a game (`POST /games/auto`).
2. Frontend opens WebSocket (`/ws/games/{gameId}`).
3. Backend runs bidding, trump selection, and play-state transitions.
4. Bots decide actions via rollout/minimax logic.
5. Frontend renders state updates in real time.

Core behavior:
- turn-based bidding (R1/R2)
- trump selection and reveal flow
- trick-by-trick play resolution
- game-over + new-game rotation

## Repository Structure

```
backend/
  app/
    api/           # REST + WebSocket routes
    engine/        # game state machine, rules, k policy
    bots/          # rollout/minimax bot logic
  Dockerfile

frontend/
  src/
    components/    # table/player/panel/trick UI pieces
    pages/         # App pages (start/game/mobile redirect)
    hooks/         # WebSocket hook
    styles/        # SCSS styling
```

## Prerequisites

- Python 3.10+
- Node.js 18+ (20+ recommended)
- npm
- (Optional for deployment) Google Cloud SDK, Vercel CLI

## Local Run (Recommended)

Run backend and frontend in separate terminals.

### 1) Backend setup

From repo root:

```bash
cd backend
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

macOS/Linux:
```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create/update backend env:

```bash
copy .env.profile1.example .env
```

or edit existing `backend/.env` manually.

Start backend:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### 2) Frontend setup

From repo root:

```bash
cd frontend
npm install
```

Create/update frontend env:

```bash
copy .env.profile1.example .env
```

For local backend, use:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_WS_BASE_URL=ws://127.0.0.1:8000
```

Start frontend:

```bash
npm run dev
```

Open:

```text
http://localhost:5173
```

## Environment Variables

### Backend (`backend/.env`)

Most important variables:

| Variable | Meaning | Typical value |
|---|---|---|
| `APP_K_OVERRIDE` | Force fixed search depth `k` for all tricks | `1`, `2`, `3`, or empty |
| `APP_ROLLOUTS` | Rollouts per decision | `150-500` |
| `APP_WORKERS` | Process pool workers | `2-12` |
| `APP_MAX_CONCURRENT_BOT_THINKING` | Max simultaneous bot computations per instance | `1-4` |
| `APP_ROLLOUT_BACKEND` | `local` or `ray` rollout backend | `local` |
| `APP_ROLLOUT_DEAL_RETRIES` | Constraint deal retries in rollout generation | `30` |
| `APP_CORS_ORIGINS` | Comma-separated allow-list for frontend origins | `https://your-app.vercel.app` |
| `APP_CORS_ORIGIN_REGEX` | Optional regex for preview domains | `^https://.*\.vercel\.app$` |
| `APP_FIXED_DECK_ENABLED` | Deterministic fixed-deck mode | empty or `1` |
| `APP_FIXED_DECK_PATH` | Path to fixed deck file | `backend/fixed_deck.txt` |

Current defaults are parsed in `backend/app/settings.py`.

### Frontend (`frontend/.env`)

| Variable | Meaning |
|---|---|
| `VITE_API_BASE_URL` | HTTP base URL for REST calls |
| `VITE_WS_BASE_URL` | WebSocket base URL |

## K Policy And Search Depth Tuning

Search depth is computed in `backend/app/engine/k_policy.py`.

Current policy:
- if `APP_K_OVERRIDE` is set, backend always uses that value
- otherwise dynamic:
  - catches 1-2: `k=2`
  - catches 3-4: `k=3`
  - catches 5-8: `k=max(1, 9-catch_number)`

### Fastest profile (public users)

Use:

```env
APP_K_OVERRIDE=1
APP_ROLLOUTS=150-250
```

This minimizes compute and increases throughput.

### Deeper search (stronger bots, slower responses)

Option A: fixed depth via env

```env
APP_K_OVERRIDE=2
```

or

```env
APP_K_OVERRIDE=3
```

Option B: dynamic policy edit

Edit `compute_k()` in `backend/app/engine/k_policy.py` and remove override (`APP_K_OVERRIDE=`).

Example idea:
- early game deeper (`k=3` or `k=4`)
- late game shallower (`k=1` or `k=2`)

### Important

Any `.env` or `k_policy.py` change requires backend restart/redeploy.

## Performance Notes

- Increasing `k` and `APP_ROLLOUTS` improves strength but increases latency and CPU usage.
- `APP_WORKERS` should generally not exceed available vCPU count by much.
- `APP_MAX_CONCURRENT_BOT_THINKING` controls cross-game bot compute parallelism per backend instance.

Game state storage is in-memory (`GameManager._games`), so server restarts clear active games.

## Build

Frontend production build:

```bash
cd frontend
npm run build
```

Backend syntax sanity:

```bash
python -m py_compile backend/app/main.py backend/app/settings.py
```

## Deployment

For public profile deployment (Vercel frontend + Cloud Run backend), use:

- `DEPLOY_PROFILE_1.md`

It includes:
- Cloud Build image command
- Cloud Run deployment flags
- recommended env values for `APP_K_OVERRIDE=1`

## Screenshots

# Bidding
<img width="2559" height="1273" alt="image" src="https://github.com/user-attachments/assets/0949b299-d6de-489c-a61a-aa9b548ecd5d" />

# Gameplay
<img width="2559" height="1247" alt="image" src="https://github.com/user-attachments/assets/fced50a8-6cbd-4b5c-a97b-102d5f5431b4" />

# Crushing Defeat
<img width="2559" height="1250" alt="image" src="https://github.com/user-attachments/assets/be43f937-9401-4597-9eb4-c6bcbd10068c" />

