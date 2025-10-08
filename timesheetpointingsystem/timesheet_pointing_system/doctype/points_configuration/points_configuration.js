frappe.ui.form.on("Criteria and Points", {
	criteria: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (!row || !row.criteria) return;
		let duplicate = false;
		for (let i = 0; i < frm.doc.criteria_and_pts.length - 1; i++) {
			if (frm.doc.criteria_and_pts[i].criteria === row.criteria) duplicate = true;
		}

		if (duplicate) {
			frm.get_field("criteria_and_pts").grid.grid_rows_by_docname[cdn].remove();
			frappe.msgprint("Criteria already exist");
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
