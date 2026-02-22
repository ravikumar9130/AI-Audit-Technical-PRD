# Frontend

Next.js 14 application with role-based dashboards.

## Structure

- `app/` - Next.js App Router
  - `dashboard/` - Role-based dashboard pages
    - `agent/` - Agent cockpit view
    - `manager/` - Team war room view
    - `cxo/` - Executive view
  - `api/` - API routes
  - `components/` - Shared components
- `components/ui/` - ShadCN UI components
- `lib/` - Utilities, hooks, API clients

## Development

```bash
cd frontend
npm install
npm run dev
```

## Features

- Role-based access control
- Real-time WebSocket updates
- Drag-and-drop file upload
- Interactive dashboards with charts
- Dark mode support
- Mobile responsive

## Environment Variables

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```
