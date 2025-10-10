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
			"holiday_list",
		];

		fields.forEach((f) => frm.set_df_property(f, "hidden", hide));
	},
});
