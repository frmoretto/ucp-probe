# ucp-probe

**What a permissionless agent can actually do on a live Shopify store.**

A tiny, dependency-free research probe that walks Shopify's new agentic-commerce surface (UCP / MCP) on a **live, named** storefront, as an **unsigned, anonymous** agent — no API key, no merchant permission, no installed app, ~one file of code.

> ⚠️ **This is a read + cart research probe. It does NOT complete purchases.** It stops at Shopify's documented buyer-approval gate and never calls `complete_checkout`. No payment instruments, no PII, no orders.

---

## The finding (verified May 2026, against `allbirds.com`)

An anonymous agent, starting from the store's own public text files, can **read the full catalog** and **create a cart** — permissionlessly, by Shopify's own design. The wall is at **checkout**, and it isn't the merchant's access control. It's **buyer consent**.

| Step | Anonymous, unsigned agent | Corroborated by |
|---|---|---|
| Discover (`robots.txt` → `llms.txt` → `agents.md` → `/.well-known/ucp`) | ✅ open | live |
| `search_catalog` / `lookup_catalog` (read) | ✅ clean | Shopify docs — catalog access on all tiers |
| `create_cart` (write) | ✅ clean (`isError: false`) | Shopify Cart MCP doc: *"Cart tools accept unauthenticated requests."* |
| `create_checkout` | ⚠️ returns a reference but `isError: true`, status `requires_escalation` | live |
| pay / `complete_checkout` | ⛔ **buyer consent required** (`requires_buyer_input`, hands off via `continue_url`) — **not called** | `agents.md`: *"Checkout requires human approval."* |

**So:** read and cart are open to anyone's agent on a live store. The checkout call bounces straight to a human-approval gate. Your access control is not what protects the transaction — the buyer's consent is, by protocol design.

---

## This is not a "first" — and the gate is universal

UCP agents already exist: Shopify's own reference demos, open-source agents, and a credentialed team called **CartAI** that publicly documented the *same* read → cart → checkout flow on live Shopify merchants — at the **Token tier** (full Bearer credentials) — and hit the **identical wall** at `complete_checkout` (`checkout_completion_ineligible` / `requires_escalation`). See their thread: <https://community.shopify.dev/t/seeking-guidance-on-complete-checkout-for-agentic-commerce-platform/34484>.

That makes the buyer-consent gate **universal across tiers** — anonymous *and* fully credentialed agents both route the payment back to a human.

What this repo adds is the **floor**: how far an agent gets with *no credentials at all*, on a *named* store, and the emphasis that **read and cart are permissionless**. Treat it as a field report, not a first.

---

## Reproduce it

Pure Python 3 standard library — no `pip install`.

```bash
python probe.py                       # discovery + catalog read (default: allbirds.com)
python probe.py --cart                # also create an ephemeral cart
python probe.py --cart --checkout     # also attempt checkout -> shows the requires_escalation wall
python probe.py --store gymshark.com --query "running shorts"
```

The script never calls `complete_checkout`. Other stores known live at time of writing: `gymshark.com`, `kyliecosmetics.com`. (Hydrogen/React storefronts like `skims.com` serve `/.well-known/ucp` but not the `/llms.txt`/`/agents.md` text files; non-enrolled stores 404 everything.)

---

## How the tool surface works (capability negotiation)

UCP negotiates an agent's available tools as the **intersection** of what the agent's profile declares and what the merchant offers. So the profile you present decides your tool surface:

- [`ucp-agent-profile.json`](ucp-agent-profile.json) — declares only `catalog.search` / `catalog.lookup` → you get **read tools only** (`create_cart` returns *"Tool not found"*).
- [`ucp-agent-profile-full.json`](ucp-agent-profile-full.json) — also declares `cart` + `checkout` → those tools appear and work unsigned (up to the buyer gate).

Both profiles are **unsigned, self-hosted JSON** — no key, no registration, no signature. Every MCP call still requires a profile *URI* (served as `application/json`; this repo's files are delivered via jsDelivr).

---

## Responsible use

- **Reads and ephemeral carts only. No purchases.** The probe stops exactly where `agents.md` says agents must stop, and never calls `complete_checkout`.
- No payment instruments, no buyer PII.
- Uses only the **public, default** endpoints Shopify ships on every enabled store.
- Identify your agent honestly (the default `User-Agent` does), and back off on `429`.
- Carts/checkouts created are ephemeral references that expire; nothing is charged.

---

## References

- Shopify agent docs: <https://shopify.dev/docs/agents>
- Cart MCP (unauthenticated): <https://shopify.dev/docs/agents/carts-and-checkout/cart-mcp> · Auth & trust tiers: <https://shopify.dev/docs/agents/profiles/auth-and-rate-limiting>
- UCP specification: <https://ucp.dev>
- Token-tier precedent (CartAI): <https://community.shopify.dev/t/seeking-guidance-on-complete-checkout-for-agentic-commerce-platform/34484>

Built as field research for *Selling to Agents* (Francesco Marinoni Moretto), a merchant-facing playbook on agentic commerce.

## License

MIT — see [LICENSE](LICENSE).
