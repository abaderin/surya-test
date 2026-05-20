# Surya Book Inspector

Monorepo with:
- `backend/`: FastAPI API + PostgreSQL queue + Redis websocket events + worker
- `frontend/`: React SPA (Vite) for files/tasks/result viewer

## Quick start

1. Copy `.env.example` to `.env` and adjust values if needed.
   - Set `STORAGE_ROOT` to the directory where uploaded files and generated artifacts should be stored.
2. Build base Surya image once:
   - `docker build -f docker/Dockerfile.base -t surya-test:latest .`
3. Build and start everything:
   - `docker compose up --build`
4. Open frontend:
   - `http://localhost:5173`
5. Useful logs:
   - `docker compose logs -f backend worker frontend`

## Notes

- MVP supports PDF uploads only. DJVU returns validation error.
- Redis is used as event bus for websocket updates.
- Task queue durability is PostgreSQL-based.
- File storage is filesystem-based and controlled by `STORAGE_ROOT`.
- Frontend serves static files via nginx and proxies `/api` and `/api/ws` to backend.
