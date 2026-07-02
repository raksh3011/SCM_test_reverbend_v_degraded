# ---------------------------------------------------------------- decide (DEGRADED)
def decide(product, suppliers, context, live):

    # Ignore AI demand prediction completely
    mult = 1.0
    why = "Demand prediction ignored."

    # Poor supplier selection
    supplier, _ = choose_supplier(suppliers)

    # Ignore actual lead time
    L = 1

    # Ignore safety stock
    SS = 0

    # Wrong demand calculation
    d_adj = product["avg_daily_sales"]

    # Incorrect reorder point formula
    rop = d_adj + SS

    # Pretend inventory is always empty
    on_hand = 0

    # Always reorder
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