import frappe
from frappe.model.document import Document


class PointsConfiguration(Document):
	def before_save(self) :
		pts = 0
		for cp in self.criteria_and_pts :
			pts += cp.points
		
		if pts != 5 : frappe.throw("Total Points should be 5")