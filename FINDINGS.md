# Findings — live UCP probe

**Run:** 2026-05-31 · **Target:** `allbirds.com` (live, named Shopify storefront) · **Agent:** unsigned, self-hosted JSON profile, no key, no permission, no installed app.

All values below were captured live from primary endpoints. This is a read + cart probe; `complete_checkout` was never called and nothing was purchased.

## The walk

| # | Step | Call | Result |
|---|------|------|--------|
| 0 | `GET /robots.txt` | — | 200. Blocks human paths (`/cart`, `/checkout`, `/orders`, `/account`, `/search`) and a few crawlers; **names no AI agent** and does **not** disallow `/llms.txt`, `/agents.md`, `/.well-known/ucp`, or `/api/ucp/mcp`. |
| 1 | `GET /llms.txt`, `/agents.md` | — | 200, `text/markdown`. Agent instructions + a documented Discover→Search→Cart→Checkout→Fulfill→Complete flow, with a "Read-Only Browsing (No Authentication Required)" section and "Checkout requires human approval." |
| 2 | `GET /.well-known/ucp` | — | 200, `application/json`. UCP `2026-04-08`; MCP endpoint = `weareallbirds.myshopify.com/api/ucp/mcp`; 8 capabilities; Google Pay (`auth_jwt: ""`) + Shopify Card handlers. |
| 3 | `search_catalog` | read | ✅ 10 products. Men's/Women's Wool Runner, **$110.00** (`amount: 11000 USD`). |
| 4 | `lookup_catalog` | read | ✅ success. |
| 5 | `create_cart` | write | ✅ **clean (`isError: false`)** — `gid://shopify/Cart/hWNCnbBvJyVXIZVRbPpu2a6l`, total **$110**. |
| 6 | `create_checkout` | write | ⚠️ returns a checkout reference (`gid://shopify/Checkout/hWNCnbHcBNl9F5BNrR4UKm15`, $110) **flagged `isError: true`**, status **`requires_escalation`**. |
| 7 | pay | — | ⛔ `payment.instruments: []`; message **"An extension interaction is required to complete the checkout"**, severity **`requires_buyer_input`**; `continue_url` hands off to a human. **`complete_checkout` not called.** |

## What it means

- **Read and cart are permissionless** for an unsigned/anonymous agent — corroborated by Shopify's Cart MCP doc (*"Cart tools accept unauthenticated requests"*) and the auth-tier table (catalog access on all tiers).
- **The wall is buyer consent, not merchant access control.** `create_checkout` bounces straight to `requires_escalation` / `requires_buyer_input`. An anonymous agent gets a clean *cart*, not a completable *checkout*.
- **The gate is universal across tiers.** A credentialed team (CartAI) publicly documented the same flow at the **Token tier** and hit the identical wall at `complete_checkout` (`checkout_completion_ineligible` / `requires_escalation`). The buyer-consent gate applies regardless of agent identity.
- **`robots.txt` doesn't govern the agent channel.** It guards human web paths; the agentic surface (MCP) is a separate, unblocked channel.

## Capability negotiation (why "Tool not found" appears first)

The agent's tool surface is the **intersection** of the capabilities its profile declares and those the merchant offers. The read-only profile (`ucp-agent-profile.json`) declares only `catalog.*`, so `create_cart` returned *"Tool not found"* until the cart-declaring profile (`ucp-agent-profile-full.json`) was used — at which point cart/checkout tools appeared and worked unsigned (up to the buyer gate).

## Scope / cross-store notes

- Live & enabled at run time: `allbirds.com`, `gymshark.com`, `kyliecosmetics.com` (Liquid themes).
- `skims.com` (Hydrogen/React): serves `/.well-known/ucp` at the platform level but 404s `/llms.txt` and `/agents.md` — the text-file routes aren't ported to the custom storefront.
- `fashionova.com`, `bombas.com`: not enrolled (404 across the board) at run time.

## Reproduce

```bash
python probe.py --store allbirds.com --cart --checkout
```

Not legal, security, or investment advice. Behavior reflects the platform state on the run date and may change.
