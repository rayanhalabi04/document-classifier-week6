# Document Classifier Frontend

Minimal React/Vite demo UI for the internal Document Classification Service.

## Setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The frontend expects the FastAPI API at:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

During `npm run dev`, Vite proxies API paths to `http://localhost:8000`, so browser requests use relative URLs and avoid local CORS issues. Production builds use `VITE_API_BASE_URL`.

## Backend Endpoints Used

- `POST /auth/jwt/login`
- `GET /users/me`
- `GET /users`
- `POST /users/invitations`
- `PUT /users/{user_id}/roles`
- `GET /batches`
- `GET /batches/{batch_id}`
- `GET /predictions/recent`
- `GET /predictions/{prediction_id}`
- `GET /predictions/{prediction_id}/overlay`
- `POST /predictions/{prediction_id}/review`
- `GET /audit-events`

## Assumptions

- Login uses the FastAPI Users form payload: `username` and `password`.
- The current-user endpoint is `GET /users/me`.
- Role management prefers `PUT /users/{user_id}/roles`, although the backend also exposes `PUT /roles/{user_id}`.
- Prediction review sends `{ "reviewed_label": "..." }`.
- When any API call fails during local development, the UI falls back to demo data and shows a banner.

## Demo Roles

Use real backend accounts for the best demo. The UI routes users by roles returned from `GET /users/me`:

- `admin`: Admin, Batches, Predictions, Audit
- `reviewer`: Reviewer Queue, Batches, Predictions
- `auditor`: Auditor View, Batches, Audit

The scanner/vendor is intentionally not a dashboard role; the flow is shown in the overview as SFTP ingestion.
