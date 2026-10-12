# DocSummarizer: Front-end

Next.js 16 (App Router, Cache Components) + React 19 + Tailwind CSS 4.
See the [project README](../README.md) for the full picture.

```powershell
npm install
npm run dev      # http://localhost:3000
```

The back-end must be running (see [`../back-end`](../back-end/readme.md)). By default
the app calls port 8000 on the same host it was opened from. To use a different
address, copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL`.

| Route | Screen |
|-------|--------|
| `/` | Upload a document, choose the length, generate (shows processing steps) |
| `/summary?doc=…&summary=…` | Summary, download/copy, other lengths, feedback form |
| `/history` | Uploaded documents |
| `/feedback` | Feedback statistics and recent ratings |

All back-end calls live in [`lib/api.js`](lib/api.js).
