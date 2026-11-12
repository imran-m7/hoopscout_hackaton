<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

## What Lovable manages

Rules outside this block are the project's own. Change the pieces below in
Lovable, not by hand. With the [Lovable MCP](https://mcp.lovable.dev)
connected, `send_message` asks Lovable to do it; otherwise ask the user to
use the editor.

- **Database.** Do not add or edit `supabase/migrations/` or `drizzle/`.
  Ask Lovable to change the schema.
- **Generated files.** Do not edit a file whose header says it is automatically
  generated.
- **AI gateway.** Keep model calls on Lovable's gateway, and keep
  `LOVABLE_API_KEY` out of browser code.
- **Connectors.** Lovable provides native connectors. `list_connectors` shows
  which are enabled; `add_connector` only returns the dashboard link. When a
  connector is enabled, calls go through the connector gateway and need
  `LOVABLE_API_KEY`. When Lovable does not provide one, users can bring their
  own key and store it in Secrets.
- **Secrets.** Lovable manages them. Do not put secret values in the repo.
<!-- LOVABLE:END -->

## Project rules
- Frontend only: all backend calls live in `src/lib/api.ts`, which falls back to `src/mocks/` when the Python API is unreachable or `VITE_USE_MOCK=true` — the app must never blank out when the API is down.
- `src/lib/types.ts` mirrors the Python API contract exactly (snake_case); never rename fields.
- Ranking/weights/hidden-gem logic lives in `src/lib/scoring.ts` and is recomputed client-side; covered by `src/test/scoring.test.ts`.
- Role, shortlist and scout notes are localStorage only (`src/lib/storage.ts`); no auth or database.
- Role access rules live in `src/lib/access.ts` (tested in `src/test/access.test.ts`); pages wrap content with guards from `src/components/hoop/Access.tsx`.
