frappe.ui.form.on("Criteria and Points", {
    criteria : function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (!row || !row.criteria) return;
        let duplicate = frm.doc.criteria_and_pts.some(
            element => element.criteria === row.criteria
        );

        if(duplicate) {
            setTimeout(() => {
                frm.get_field("criteria_and_pts").grid.grid_rows_by_docname[cdn].remove();
                frappe.msgprint(__("Criteria already exist"));
            },1);
        }
    }
});
