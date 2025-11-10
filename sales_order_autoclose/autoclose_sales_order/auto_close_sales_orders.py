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
    """Return True if any linked document exists against this Sales Order."""
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
    """
    Auto close Sales Orders if:
      - 'Autoclose after 60 days' is ticked
      - docstatus = 1
      - status not in Closed/Cancelled/On Hold
      - transaction_date <= cutoff_date
      - No linked documents
    """
    try:
        # Debug: current executing user
        frappe.logger().info(f"[AutoClose] Running as user: {frappe.session.user}")

        cutoff_date = getdate(add_days(nowdate(), -int(days)))
        frappe.logger().info(f"[AutoClose] Cutoff date = {cutoff_date}")

        # Fetch eligible orders
        sales_orders = frappe.db.get_all(
            "Sales Order",
            filters={
                "autoclose_after_60_days": 1,
                "docstatus": 1,
                "status": ["not in", ["Closed", "Cancelled", "On Hold"]],
                "transaction_date": ("<=", cutoff_date),
            },
            fields=["name", "transaction_date", "customer"],
        )

        frappe.logger().info(
            f"[AutoClose] Candidates: {[s['name'] for s in sales_orders]}"
        )

        if not sales_orders:
            frappe.logger().info("[AutoClose] No eligible Sales Orders found.")
            return

        # Filter by linked transactions
        to_close = []
        for so in sales_orders:
            if not _has_linked_transactions(so["name"]):
                to_close.append(so["name"])
            else:
                frappe.log_error(
                    f"SO {so['name']} skipped — linked documents exist.",
                    "AutoClose Skip"
                )

        frappe.logger().info(f"[AutoClose] Final to-close list: {to_close}")

        if not to_close:
            frappe.logger().info("[AutoClose] No orders to close.")
            return

        # ------------------------------------------------------------
        # ✅ FORCED CLOSE (Fix for Frappe Cloud restrictions)
        # ------------------------------------------------------------
        for name in to_close:
            try:
                doc = frappe.get_doc("Sales Order", name)
                doc.flags.ignore_permissions = True
                doc.flags.ignore_links = True

                # Force status to Closed
                doc.set("status", "Closed")
                doc.db_update()

                # Add comment
                doc.add_comment(
                    "Comment",
                    f"✅ Auto-closed by Sales Order Autoclose App (no activity for {days} days)."
                )

                frappe.logger().info(
                    f"[AutoClose] Force-closed successfully: {name}"
                )

            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"[AutoClose] Force-close failed for {name}"
                )

        # Commit changes
        frappe.db.commit()
        frappe.logger().info(
            f"[AutoClose] Successfully force-closed: {to_close}"
        )

        print(f"✅ Auto-closed Sales Orders: {', '.join(to_close)}")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "[AutoClose] Job Failed")


# import frappe
# import json
# from frappe.utils import getdate, nowdate, add_days

# LINK_DOCTYPES = [
#     ("Delivery Note", "against_sales_order"),
#     ("Sales Invoice", "sales_order"),
#     ("Work Order", "sales_order"),
#     ("Stock Entry", "sales_order"),
# ]


# def _has_linked_transactions(so_name):
#     """Return True if any linked document exists against this Sales Order."""
#     for dt, link_field in LINK_DOCTYPES:
#         try:
#             if frappe.db.exists(dt, {link_field: so_name}):
#                 return True
#         except Exception:
#             frappe.log_error(frappe.get_traceback(), f"[AutoClose] Error checking {dt}")
#     return False


# def auto_close_sales_orders(days=60):
#     """
#     Close Sales Orders automatically if:
#       - 'Autoclose after 60 days' is ticked
#       - docstatus = 1
#       - status not in Closed/Cancelled/On Hold
#       - transaction_date older than (today - days)
#       - No linked Delivery Note / Sales Invoice / Work Order / Stock Entry
#     """
#     try:
#         cutoff_date = getdate(add_days(nowdate(), -int(days)))
#         frappe.logger().info(f"[AutoClose] cutoff_date = {cutoff_date}")

#         sales_orders = frappe.db.get_all(
#             "Sales Order",
#             filters={
#                 "autoclose_after_60_days": 1,
#                 "docstatus": 1,
#                 "status": ["not in", ["Closed", "Cancelled", "On Hold"]],
#                 "transaction_date": ("<=", cutoff_date),
#             },
#             fields=["name", "transaction_date", "customer"],
#         )

#         frappe.logger().info(f"[AutoClose] Found {len(sales_orders)} candidates.")

#         if not sales_orders:
#             print("✅ No Sales Orders eligible for auto-close.")
#             return

#         to_close = []
#         for so in sales_orders:
#             if not _has_linked_transactions(so["name"]):
#                 to_close.append(so["name"])
#             else:
#                 frappe.log_error(
#                     f"Sales Order {so['name']} not closed — linked documents exist.",
#                     "AutoClose Skip"
#                 )

#         if not to_close:
#             print("⚠️ All candidates had linked transactions; nothing to close.")
#             return

#         close_fn = frappe.get_attr(
#             "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders"
#         )
#         names_json = json.dumps(to_close)

#         try:
#             close_fn(names=names_json, status="Closed")
#         except TypeError:
#             close_fn(names_json, "Closed")

#         # Add comments and update statuses
#         for name in to_close:
#             try:
#                 doc = frappe.get_doc("Sales Order", name)
#                 doc.add_comment(
#                     "Comment",
#                     f"✅ Auto-closed by Sales Order Autoclose App (no activity for {days} days)."
#                 )
#                 doc.update_status()
#             except Exception:
#                 frappe.log_error(frappe.get_traceback(), f"[AutoClose] Post-close failed for {name}")

#         # ✅ Single commit after all updates (no deadlocks)
#         frappe.db.commit()

#         print(f"✅ Auto-closed Sales Orders: {', '.join(to_close)}")
#         frappe.logger().info(f"[AutoClose] Closed {len(to_close)} Sales Orders.")

#     except Exception:
#         frappe.log_error(frappe.get_traceback(), "[AutoClose] Job Failed")
