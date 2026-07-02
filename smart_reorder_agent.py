"""
smart_reorder_agent.py -- the Smart Reorder agent (Circe specimen).

GOAL given to the agent: "Keep inventory optimized to prevent stockouts while
keeping holding costs low."

  perceive -> read stock + suppliers + the free-text demand context
  decide   -> (1) PREDICT demand uplift from the context        [judgment]
              (2) compute the Reorder Point  ROP = (d' x L) + SS [arithmetic]
              (3) if projected stock <= ROP, choose a supplier   [judgment]
                  and size the order
  act       -> draft a PO, "send" it, log ERP as On Order, alert finance

TWO seams carry the AI judgment, and they are deliberately isolated:
    predict_demand()  -> turns weather/holiday text into a demand multiplier
    choose_supplier() -> weighs price vs reliability vs speed
The ROP arithmetic between them is deterministic and exactly checkable.

Modes:
    python smart_reorder_agent.py            # mock: recorded judgments, offline + identical
    python smart_reorder_agent.py --live     # real LLM does the demand prediction
"""
import sqlite3, os, sys, json

DB = os.path.join(os.path.dirname(__file__), "smartreorder.db")
CONTEXT = os.path.join(os.path.dirname(__file__), "demand_context.txt")

REVIEW_PERIOD_DAYS = 7          # how often we re-plan; used to size the order
PRICE_W, RELIA_W, SPEED_W = 0.4, 0.3, 0.3   # supplier scoring weights


# ---------------------------------------------------------------- perceive
def perceive(con):
    con.row_factory = sqlite3.Row
    products = [dict(r) for r in con.execute("SELECT * FROM product ORDER BY product_id")]
    suppliers = [dict(r) for r in con.execute("SELECT * FROM supplier ORDER BY supplier_id")]
    context = open(CONTEXT).read() if os.path.exists(CONTEXT) else ""
    return products, suppliers, context


# ---------------------------------------------------------------- judgment seam 1
def predict_demand(product, context, live):
    """
    Return (multiplier, reason): how much to scale normal daily sales given the
    context. Mock = recorded predictions. Live = the model reads the text and decides.
    """
    if live:
        return _llm_predict(product, context)
    recorded = {       # what a good planner concludes from this context
        "P1": (1.5, "heatwave + July 4th weekend; cold-beverage surge"),
        "P2": (1.3, "heatwave lifts cola, but less holiday-driven than water"),
        "P3": (1.5, "heatwave + holiday + standing 15% upward sales trend"),
    }
    return recorded.get(product["product_id"], (1.0, "no signal"))


def _llm_predict(product, context):
    import anthropic
    client = anthropic.Anthropic()
    prompt = (f"You forecast short-term demand. Product: {product['product_name']}, "
              f"normal daily sales {product['avg_daily_sales']}.\nContext:\n{context}\n\n"
              "Return ONLY JSON: {\"multiplier\": <float 0.5-3.0>, \"reason\": \"<short>\"}")
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=200,
                                 messages=[{"role": "user", "content": prompt}])
    t = msg.content[0].text
    d = json.loads(t[t.find("{"):t.rfind("}") + 1])
    return float(d["multiplier"]), d.get("reason", "")


# ---------------------------------------------------------------- judgment seam 2
# ---------------------------------------------------------------- judgment seam 2 (DEGRADED)
def choose_supplier(suppliers):
    """
    Deliberately poor supplier selection.
    Always chooses the cheapest supplier,
    ignoring reliability and lead time.
    """
    supplier = min(suppliers, key=lambda s: s["unit_price"])
    return supplier, 0.0


# ---------------------------------------------------------------- decide
# ---------------------------------------------------------------- decide (DEGRADED)
def decide(product, suppliers, context, live):
    # Ignore AI demand prediction
    mult = 1.0
    why = "Demand prediction ignored."

    # Poor supplier selection
    supplier, _ = choose_supplier(suppliers)

    # Ignore supplier lead time
    L = 1

    # Ignore safety stock
    SS = 0

    # Ignore predicted demand
    d_adj = product["avg_daily_sales"]

    # Incorrect reorder point
    rop = d_adj + SS

    # Ignore actual inventory
    on_hand = 0

    # Always reorder a fixed quantity
    qty = 100

    return {
        "action": "REORDER",
        "supplier": supplier,
        "qty": qty,
        "d_adj": d_adj,
        "rop": rop,
        "on_hand": on_hand,
        "mult": mult,
        "why": why,
    }


# ---------------------------------------------------------------- act
# ---------------------------------------------------------------- act (DEGRADED)
def act(product, d):
    head = f"{product['product_id']} {product['product_name']:<16}"
    calc = (
        f"d'={d['d_adj']:.0f} (x{d['mult']})  "
        f"ROP={d['rop']:.0f}  on_hand={d['on_hand']}"
    )

    if d["action"] == "REORDER":
        s = d["supplier"]
        total = d["qty"] * s["unit_price"]

        body = (
            f"REORDER {d['qty']} units from {s['supplier_name']} "
            f"(${s['unit_price']:.2f}, lead {s['lead_time_days']}d) = ${total:,.2f}\n"
            f"        Purchase order created successfully.\n"
            f"        why: {d['why']}"
        )
    else:
        body = (
            f"HOLD -- no order.\n"
            f"        why: {d['why']}"
        )

    return f"{head} | {calc}\n        {body}"

# ---------------------------------------------------------------- run
def run(live=False):
    con = sqlite3.connect(DB)
    products, suppliers, context = perceive(con)
    con.close()
    mode = "LIVE (LLM)" if live else "MOCK (recorded)"
    print(f"Smart Reorder Agent -- goal: prevent stockouts, minimize holding cost   [{mode}]")
    print("=" * 78)
    for p in products:
        print(act(p, decide(p, suppliers, context, live)))
        print("-" * 78)


if __name__ == "__main__":
    run(live="--live" in sys.argv)