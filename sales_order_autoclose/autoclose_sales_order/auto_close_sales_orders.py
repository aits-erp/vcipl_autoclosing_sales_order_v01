import frappe
import json
from frappe.utils import getdate, nowdate, add_days

LINK_DOCTYPES = [
    ("Delivery Note", "against_sales_order"),
    ("Sales Invoice", "sales_order"),
    ("Work Order", "sales_order"),
    ("Stock Entry", "sales_order"),
]


def _has_linked_transactions(so_name):
    for dt, link_field in LINK_DOCTYPES:
        try:
            if frappe.db.exists(dt, {link_field: so_name}):
                return True
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"[AutoClose] Error checking link for {dt}"
            )
    return False


def auto_close_sales_orders(days=60):
    try:
        frappe.logger().info(f"[AutoClose] Running as user: {frappe.session.user}")

        cutoff_date = getdate(add_days(nowdate(), -int(days)))
        frappe.logger().info(f"[AutoClose] Cutoff date = {cutoff_date}")

        # Fetch candidates
        sales_orders = frappe.db.get_all(
            "Sales Order",
            filters={
                "autoclose_after_60_days": 1,
                "docstatus": 1,
                "status": ["not in", ["Closed", "Cancelled", "On Hold"]],
                "transaction_date": ("<=", cutoff_date),
            },
            fields=["name", "transaction_date"],
        )

        frappe.logger().info(f"[AutoClose] Candidates: {[s['name'] for s in sales_orders]}")

        if not sales_orders:
            frappe.logger().info("[AutoClose] No eligible orders.")
            return

        to_close = []
        for so in sales_orders:
            if not _has_linked_transactions(so["name"]):
                to_close.append(so["name"])

        frappe.logger().info(f"[AutoClose] Final to-close list: {to_close}")

        if not to_close:
            frappe.logger().info("[AutoClose] Nothing to close.")
            return

        # ------------------------------------------------------------
        # ✅ ✅ FORCE CLOSE VIA SQL (cloud proof)
        # ------------------------------------------------------------
        for name in to_close:
            try:
                # Direct DB update (bypass validation)
                frappe.db.sql("""
                    UPDATE `tabSales Order`
                    SET status='Closed'
                    WHERE name=%s
                """, (name,))

                # Add comment normally
                doc = frappe.get_doc("Sales Order", name)
                doc.add_comment(
                    "Comment",
                    f"✅ Auto-closed by Sales Order Autoclose App (no activity for {days} days)."
                )

                frappe.logger().info(f"[AutoClose] Force SQL close OK: {name}")

            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"[AutoClose] SQL force-close failed for {name}"
                )

        frappe.db.commit()
        frappe.logger().info(f"[AutoClose] Completed SQL force-close for: {to_close}")

        print(f"✅ Auto-closed Sales Orders: {', '.join(to_close)}")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "[AutoClose] Job Failed")
