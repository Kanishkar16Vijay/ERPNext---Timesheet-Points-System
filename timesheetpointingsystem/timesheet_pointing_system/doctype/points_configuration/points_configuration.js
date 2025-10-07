frappe.ui.form.on("Criteria and Points", {
	criteria: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (!row || !row.criteria) return;
		let duplicate = frm.doc.criteria_and_pts.some(
			(element) => element.criteria === row.criteria
		);

		if (duplicate) {
			setTimeout(() => {
				frm.get_field("criteria_and_pts").grid.grid_rows_by_docname[cdn].remove();
				frappe.msgprint(__("Criteria already exist"));
			}, 1);
		}
	},
});

frappe.ui.form.on("Points Configuration", {
	refresh(frm) {
		frm.trigger("toggle_fields");
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
			"criteria_and_pts",
		];

		fields.forEach((f) => frm.set_df_property(f, "hidden", hide));
	},
});
