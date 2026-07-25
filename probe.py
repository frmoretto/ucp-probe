#!/usr/bin/env python3
"""
ucp-probe — walk a live Shopify store's agentic (UCP / MCP) surface as an
UNSIGNED, ANONYMOUS agent: no API key, no installed app, no credentials —
using only the anonymous access Shopify's own design permits.

It demonstrates, on a real named storefront, that:
  - discovery (robots.txt -> llms.txt -> agents.md -> /.well-known/ucp) is open,
  - catalog READ is permissionless,
  - cart CREATE is permissionless (Shopify: "Cart tools accept unauthenticated requests"),
  - CHECKOUT bounces to a buyer-consent gate (status: requires_escalation).

It NEVER calls complete_checkout. It does not purchase anything, attach a payment
instrument, or send any buyer PII.

Usage:
  python probe.py                       # discovery + catalog read (allbirds.com)
  python probe.py --cart                # + create an ephemeral cart
  python probe.py --cart --checkout     # + attempt checkout -> shows the wall
  python probe.py --store gymshark.com --query "running shorts"

Dependencies: none (Python 3 standard library).
License: MIT.
"""
import argparse, json, urllib.request, urllib.error

# Unsigned, self-hosted agent profile. The "full" profile also declares cart +
# checkout capabilities; the read-only one is ucp-agent-profile.json.
DEFAULT_PROFILE = "https://cdn.jsdelivr.net/gh/frmoretto/ucp-probe@main/ucp-agent-profile-full.json"
UA = "ucp-probe/1.0 (+https://github.com/frmoretto/ucp-probe)"


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8", "replace")


def mcp_call(endpoint, name, arguments):
    """One UCP MCP tools/call over JSON-RPC."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode(), method="POST",
        headers={"User-Agent": UA, "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def meta(profile):
    # The agent profile URI rides in every call's arguments.meta for UCP negotiation.
    return {"ucp-agent": {"profile": profile}}


def find_products(o, depth=0):
    if depth > 6:
        return []
    if isinstance(o, dict):
        for k in ("products", "items", "results"):
            if isinstance(o.get(k), list):
                return o[k]
        for v in o.values():
            r = find_products(v, depth + 1)
            if r:
                return r
    if isinstance(o, list):
        for v in o:
            r = find_products(v, depth + 1)
            if r:
                return r
    return []


def total_cents(obj):
    for t in obj.get("totals", []):
        if t.get("type") == "total":
            return t.get("amount", 0)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Unsigned UCP probe of a live Shopify store.")
    ap.add_argument("--store", default="allbirds.com")
    ap.add_argument("--query", default="wool runner")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--cart", action="store_true", help="create an ephemeral cart")
    ap.add_argument("--checkout", action="store_true", help="attempt checkout (shows the wall); never completes")
    a = ap.parse_args()
    base = "https://" + a.store.replace("https://", "").replace("http://", "").rstrip("/")

    print(f"# ucp-probe  ->  {base}   (unsigned, anonymous; reads + cart only)\n")

    # --- Steps 0-1: discovery from the public text files ---
    for path in ("/robots.txt", "/llms.txt", "/agents.md"):
        st, ct, _ = http_get(base + path)
        print(f"[{st}] {ct.split(';')[0]:22} {path}")

    # --- Step 2: protocol discovery ---
    st, ct, body = http_get(base + "/.well-known/ucp")
    print(f"[{st}] {ct.split(';')[0]:22} /.well-known/ucp")
    if st != 200:
        print("\n  Store is not UCP-enabled (or not enrolled). Stopping.")
        return
    ucp = json.loads(body)["ucp"]
    endpoint = next(s["endpoint"] for s in ucp["services"]["dev.ucp.shopping"]
                    if s.get("transport") == "mcp")
    print(f"  MCP endpoint : {endpoint}")
    print(f"  capabilities : {', '.join(sorted(ucp['capabilities']))}")

    # --- Step 3: catalog read (permissionless) ---
    print(f"\n## search_catalog  (read)   query='{a.query}'")
    r = mcp_call(endpoint, "search_catalog", {"meta": meta(a.profile), "catalog": {"query": a.query}})
    products = find_products(r.get("result", {}).get("structuredContent", {}))
    if not products:
        print("  No products / unexpected response:", json.dumps(r)[:200])
        return
    print(f"  {len(products)} products:")
    for p in products[:5]:
        amt = (p.get("price_range", {}).get("min") or {}).get("amount", 0)
        print(f"   - {p.get('title')}  ${amt/100:.2f}")
    variant_id = products[0]["variants"][0]["id"]

    # --- Step 4: cart create (permissionless write) ---
    if a.cart or a.checkout:
        print("\n## create_cart  (write)")
        r = mcp_call(endpoint, "create_cart", {
            "meta": meta(a.profile),
            "cart": {"line_items": [{"item": {"id": variant_id}, "quantity": 1}]}})
        res = r.get("result", {})
        if res.get("isError"):
            print("  isError: true ->", json.dumps(res.get("content"))[:160])
            print("  (declare cart capability in your profile; see ucp-agent-profile-full.json)")
        else:
            cart = res.get("structuredContent", {})
            print(f"  clean success (isError: false)")
            print(f"  cart id : {cart.get('id')}")
            print(f"  total   : ${total_cents(cart)/100:.2f}")

    # --- Step 5: checkout attempt -> the buyer-consent wall. NEVER completes. ---
    if a.checkout:
        print("\n## create_checkout  (write)  -> expect the buyer-consent wall")
        r = mcp_call(endpoint, "create_checkout", {
            "meta": meta(a.profile),
            "checkout": {"line_items": [{"item": {"id": variant_id}, "quantity": 1}]}})
        res = r.get("result", {})
        try:
            co = res.get("structuredContent") or json.loads(res["content"][0]["text"])
        except Exception:
            co = {}
        print(f"  isError : {res.get('isError')}")
        print(f"  status  : {co.get('status')}")
        for m in co.get("messages", []):
            print(f"  message : [{m.get('severity')}] {m.get('content')}")
        if co.get("continue_url"):
            print(f"  continue_url (buyer handoff): {co['continue_url']}")
        print("\n  >>> STOP. complete_checkout is the buyer's job. This probe never calls it.")


if __name__ == "__main__":
    main()
