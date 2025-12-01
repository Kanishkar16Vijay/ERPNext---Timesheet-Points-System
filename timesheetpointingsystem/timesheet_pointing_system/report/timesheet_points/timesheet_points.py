import frappe
from frappe import _

from timesheetpointingsystem.points import set_points


def execute(filters=None):
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date should be less than To Date"))

	columns = [
		{"fieldname": "employee_name", "fieldtype": "Data", "label": _("Employee"), "width": 0},
		{"fieldname": "working_days", "fieldtype": "Float", "label": _("Working Days"), "width": 0},
		{"fieldname": "missed_dates", "fieldtype": "Data", "label": _("Missed Date"), "width": 300},
		{"fieldname": "worked_days", "fieldtype": "Int", "label": _("Timesheet Days"), "width": 0},
		{"fieldname": "word_count", "fieldtype": "Int", "label": _("Des Length"), "width": 0},
		{"fieldname": "total_hours", "fieldtype": "Float", "label": _("Working Hours"), "width": 0},
		{"fieldname": "total_points", "fieldtype": "Float", "label": _("Total Points"), "width": 0},
	]

	data = []

	emp_map = dict(
		frappe.get_all(
			"Employee", filters={"status": "Active"}, fields=["name", "employee_name"], as_list=True
		)
	)

	if filters.employee:
		summary, missed_date, no_wrk_days = set_points(
			filters.from_date, filters.to_date, tuple(filters.employee)
		)
	else:
		summary, missed_date, no_wrk_days = set_points(filters.from_date, filters.to_date, True)
	for emp in summary:
		emp_summary = {}
		emp_summary["employee_name"] = emp_map.get(emp.employee)
		emp_summary["working_days"] = no_wrk_days - emp.leave_days
		emp_summary["missed_dates"] = missed_date.get(emp.employee)
		emp_summary["worked_days"] = emp.worked_days
		emp_summary["word_count"] = emp.des_len
		emp_summary["total_hours"] = emp.total_hrs_worked
		emp_summary["total_points"] = emp.total_points
		data.append(emp_summary)

	return columns, data
