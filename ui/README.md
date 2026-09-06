# CyberWell Policy Assistant — UI

Vite + React + TypeScript single-page chat client. See the repo root `README.md` for setup
and how this fits into the rest of the project.

```bash
npm install
npm run dev      # http://localhost:5173, expects the API (api/app.py) on http://localhost:5000
```

`src/api.ts` reads the API's base URL from `VITE_API_BASE_URL` (default
`http://localhost:5000/api`).
