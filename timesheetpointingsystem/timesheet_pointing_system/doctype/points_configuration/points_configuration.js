frappe.ui.form.on("Points Configuration", {
	refresh(frm) {
		frm.trigger("toggle_fields");
		frm.add_custom_button("Calculate Points for custom dates", () => {
			let d = new frappe.ui.Dialog({
				title: "Calculate Points for custom dates",
				fields: [
					{
						label: "From Date",
						fieldname: "from_date",
						fieldtype: "Date",
						reqd: 1,
					},
					{
						label: "To Date",
						fieldname: "to_date",
						fieldtype: "Date",
						reqd: 1,
					},
				],
				primary_action_label: "Calculate Points",
				primary_action(values) {
					if (values.from_date > values.to_date) {
						frappe.throw("To Date can't before From Date");
					}
					d.hide();
					frappe.msgprint("Points for Custom Date has Scheduled");
					frappe.call({
						method: "timesheetpointingsystem.points.redis_queue",
						args: {
							start: values.from_date,
							end: values.to_date,
						},
					});
				},
			});
			d.show();
		});
	},

	disable(frm) {
		frm.trigger("toggle_fields");
	},

	toggle_fields(frm) {
		const hide = frm.doc.disable == 1;

		const fields = [
			"avg_working_hrs",
			"avg_char_len",
			"token",
			"chat",
			"daily",
			"weekly",
			"monthly",
			"holiday_list",
		];

		fields.forEach((f) => frm.set_df_property(f, "hidden", hide));
	},
});
