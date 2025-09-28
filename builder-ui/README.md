# polymo Builder UI

This directory contains the Vite-based frontend for the connector builder. It uses React, TypeScript, TailwindCSS, Radix UI, Radix Colors, Jotai, and MSW.

## Getting Started

```bash
npm install
npm run dev
```

MSW is enabled automatically in development. If this is the first time running the dev server, initialise the worker once:

```bash
npm run msw
```

## Building for Flask

```bash
npm run build
```

The compiled assets are emitted to `src/polymo/builder/static` as `main.js` and `main.css`. The Flask template loads these files directly.

## Testing

- `npm run lint` – ESLint
- `npm run format` – Biome formatter
- `npm run test:e2e` – Playwright E2E tests
