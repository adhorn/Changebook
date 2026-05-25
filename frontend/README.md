# Changebook Frontend

Next.js (App Router) frontend for Changebook. See the [root README](../README.md) for project context.

## Development

```bash
npm install
npm run dev
```

Opens on [http://localhost:3000](http://localhost:3000). Expects the backend API at `http://localhost:8000` (configurable via `NEXT_PUBLIC_API_URL`).

## Structure

```
app/              # Next.js App Router pages
  changes/[id]/   # Change detail and execution view
  new/            # New change form
components/       # Shared React components
lib/
  api.ts          # All backend API calls
```

## Conventions

- All API calls go through `lib/api.ts`
- Tailwind CSS for styling — no separate CSS files
- Components in `components/`, pages in `app/`

## Build

```bash
npx next build
```

This is also the frontend's CI check — a successful build confirms TypeScript compiles and pages render.
