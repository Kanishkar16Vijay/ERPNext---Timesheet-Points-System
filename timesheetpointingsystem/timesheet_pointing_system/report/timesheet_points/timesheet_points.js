// Copyright (c) 2025, Kanishkar and contributors
// For license information, please see license.txt

frappe.query_reports["Timesheet Points"] = {
	filters: [
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "MultiSelectList",
			options: "Employee",
			get_data: (txt) => {
				return frappe.db.get_link_options("Employee", txt);
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			mandatary: true,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			mandatory: true,
		},
	],
};
