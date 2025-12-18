# Card Issuance Service (Commercial-grade demo)

Stack: **FastAPI + PostgreSQL + Alembic + WeasyPrint (PDF)** + **React (Vite) + TypeScript + MUI + DataGrid + ECharts + React Query**

## Run (Docker)
```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs

## Notes
- DB is seeded automatically on backend start (`python -m app.seed`)
- Business numbers: APP-YYYY-XXXXXX, BAT-YYYY-XXXXXX, CARD-YYYY-XXXXXX
- Print forms (PDF):
  - `/api/applications/{id}/print/statement`
  - `/api/applications/{id}/print/contract`
