import frappe

def execute():
    """Add checkbox 'Autoclose after 60 days' to Sales Order if not present."""
    if not frappe.db.exists("Custom Field", {"dt": "Sales Order", "fieldname": "autoclose_after_60_days"}):
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Sales Order",
            "fieldname": "autoclose_after_60_days",
            "label": "Autoclose after 60 days",
            "fieldtype": "Check",
            "insert_after": "delivery_date",  # adjust if needed, safe default
            "in_list_view": 1,
            "description": "If checked, this Sales Order will be autoclosed after inactivity period."
        })
        custom_field.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info("Added Custom Field 'autoclose_after_60_days' to Sales Order.")
    else:
        frappe.logger().info("Custom Field 'autoclose_after_60_days' already exists — skipping.")
