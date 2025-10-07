# Copyright (c) 2025, Kanishkar and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Team(Document):
	def before_save(self):
		count = 1
		for tm in self.team_member:
			if tm.member:
				count += 1

		self.total_members = count
