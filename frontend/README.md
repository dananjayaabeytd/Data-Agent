# Data Agent UI

Next.js chat interface for the Data Agent FastAPI backend.

## Run

1. Start the backend from the repository root (see the root `README.md`).
2. Copy `.env.example` to `.env.local` and adjust `BACKEND_URL` if the API is not on `http://127.0.0.1:8000`.
3. `npm install`, then `npm run dev` and open `http://localhost:3000`.

## How it talks to the API

The browser calls `/api/sessions...` on the Next.js server. `src/app/api/[...path]/route.ts`
forwards only those session paths to `BACKEND_URL/api/v1/...` and adds `DATA_AGENT_API_KEY`
and `DATA_AGENT_USER_ID` server-side, so credentials never reach the browser and the backend
needs no CORS configuration for the UI.

## Structure

- `src/components/ChatApp.tsx` - state, session switching, and the send flow
- `src/components/MessageView.tsx` - message bubble with Markdown and word-by-word reveal
- `src/components/ThinkingIndicator.tsx` - animated "thinking" row while the agent works
- `src/components/Sidebar.tsx`, `Composer.tsx`, `Markdown.tsx`
- `src/lib/api.ts` - typed API client
