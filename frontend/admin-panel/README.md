# LotR Admin Panel

React + TypeScript + Vite admin panel for the LotR TCG server.

## Requirements

Run all commands **inside the dev container**.

## Setup

```bash
cd frontend/admin-panel
npm install
```

## Development

```bash
npm run dev       # starts on http://localhost:3001
```

By default the dev server proxies `/api` to `http://localhost:8000`.
Override with:

```bash
VITE_API_URL=http://my-server:8000 npm run dev
```

## Build

```bash
npm run build     # outputs to dist/
```

## Pages

| Route | Description |
|-------|-------------|
| `/login` | Admin login (only `is_admin=true` accounts allowed) |
| `/` | Dashboard — card stats + store pricing |
| `/users` | User management: search, Tolkien balance, moderator toggle, delete |
| `/cards` | Card management: list, add, soft-delete |

## Admin privileges

- **Admin** (`is_admin=true`): full panel access, set by server config/seed
- **Moderator** (`is_moderator=true`): in-game elevated role, grantable via Users page;
  cannot log into this panel
