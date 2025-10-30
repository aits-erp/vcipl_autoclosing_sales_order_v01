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
            frappe.log_error(frappe.get_traceback(), f"[AutoClose] Error checking {dt}")
    return False


def auto_close_sales_orders(days=60):
    """
    Close Sales Orders automatically if:
      - 'Autoclose after 60 days' is ticked
      - docstatus = 1
      - status not in Closed/Cancelled/On Hold
      - transaction_date older than (today - days)
      - No linked Delivery Note / Sales Invoice / Work Order / Stock Entry
    """
    try:
        cutoff_date = getdate(add_days(nowdate(), -int(days)))
        frappe.logger().info(f"[AutoClose] cutoff_date = {cutoff_date}")

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

        frappe.logger().info(f"[AutoClose] Found {len(sales_orders)} candidates.")

        if not sales_orders:
            print("✅ No Sales Orders eligible for auto-close.")
            return

        to_close = []
        for so in sales_orders:
            if not _has_linked_transactions(so["name"]):
                to_close.append(so["name"])
            else:
                frappe.log_error(
                    f"Sales Order {so['name']} not closed — linked documents exist.",
                    "AutoClose Skip"
                )

        if not to_close:
            print("⚠️ All candidates had linked transactions; nothing to close.")
            return

        close_fn = frappe.get_attr(
            "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders"
        )
        names_json = json.dumps(to_close)

        try:
            close_fn(names=names_json, status="Closed")
        except TypeError:
            close_fn(names_json, "Closed")

        # Add comments and update statuses
        for name in to_close:
            try:
                doc = frappe.get_doc("Sales Order", name)
                doc.add_comment(
                    "Comment",
                    f"✅ Auto-closed by Sales Order Autoclose App (no activity for {days} days)."
                )
                doc.update_status()
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"[AutoClose] Post-close failed for {name}")

        # ✅ Single commit after all updates (no deadlocks)
        frappe.db.commit()

        print(f"✅ Auto-closed Sales Orders: {', '.join(to_close)}")
        frappe.logger().info(f"[AutoClose] Closed {len(to_close)} Sales Orders.")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "[AutoClose] Job Failed")

# import frappe
# from frappe.utils import getdate, nowdate, add_days

# # Doctypes that can link to a Sales Order — used to detect open activity
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
#             # In case a doctype doesn't exist (e.g., HRMS only instance)
#             frappe.log_error(frappe.get_traceback(), f"AutoClose: Error checking links for {dt}")
#     return False


# def auto_close_sales_orders():
#     """Scheduled job to close eligible Sales Orders after 60 days."""
#     try:
#         cutoff_date = getdate(add_days(nowdate(), -1))
# #        cutoff_date = getdate(add_days(nowdate(), -60))

#         sales_orders = frappe.db.get_all(
#             "Sales Order",
#             filters={
#                 "autoclose_after_60_days": 1,
#                 "docstatus": 1,
#                 "status": ["not in", ["Closed", "Cancelled", "On Hold"]],
#                 "creation": ("<=", cutoff_date),
#             },
#             fields=["name", "creation", "customer"],
#         )

#         if not sales_orders:
#             frappe.logger().info("✅ No Sales Orders eligible for auto-close.")
#             return

#         to_close = []
#         for so in sales_orders:
#             if not _has_linked_transactions(so.name):
#                 to_close.append(so.name)
#             else:
#                 frappe.log_error(
#                     f"Sales Order {so.name} not auto-closed — linked documents exist.",
#                     "AutoClose Skip"
#                 )

#         if to_close:
#             # Call ERPNext’s built-in method
#             close_fn = frappe.get_attr("erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders")

#             try:
#                 close_fn(names=to_close, status="Closed")
#             except TypeError:
#                 # fallback for older ERPNext versions
#                 close_fn(to_close, "Closed")

#             for name in to_close:
#                 try:
#                     doc = frappe.get_doc("Sales Order", name)
#                     doc.add_comment(
#                         "Comment",
#                         "✅ Auto-closed by Sales Order Autoclose App (no activity for 60 days)."
#                     )
#                 except Exception:
#                     frappe.log_error(f"Failed to comment on {name}", "AutoClose Comment Failure")

#             frappe.logger().info(f"✅ Auto-closed Sales Orders: {', '.join(to_close)}")

#     except Exception:
#         frappe.log_error(frappe.get_traceback(), "❌ AutoClose Sales Orders Failed")
