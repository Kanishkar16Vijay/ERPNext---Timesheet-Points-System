import frappe
import requests
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday
from frappe.utils import add_days, add_months, getdate, today
from frappe.utils.pdf import get_pdf


class Points:
	def __init__(self):
		self.emp_map = dict(frappe.get_all("Employee", fields=["name", "employee_name"], as_list=True))
		self.setting = frappe.get_doc("Points Configuration")
		self.token = self.setting.get_password("token")
		self.chat = self.setting.chat
		self.avg_working_hrs = self.setting.avg_working_hrs
		self.avg_char_len = self.setting.avg_char_len
		self.holiday_list = self.setting.holiday_list or frappe.get_value(
			"Company", "Aerele Technologies", "default_holiday_list"
		)
		if not self.holiday_list:
			self.send_telegram_message(
				"Plese set default holiday list in Company or holiday list in Point Configuration"
			)

	# Sending Messages on Telegram Group Bot
	def send_telegram_message(self, msg, pdf):
		if not self.token or not self.chat:
			frappe.log_error("Missing Telegram token/chat_id", "Telegram Config Error")
			return

		url = f"https://api.telegram.org/bot{self.token}/sendMessage"
		payload = {"chat_id": self.chat, "text": msg, "parse_mode": "Markdown"}

		try:
			response = requests.post(url, data=payload)
			if response.status_code != 200:
				frappe.log_error(response.text, "Telegram Message Error")
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Telegram Message Failed")

		url = f"https://api.telegram.org/bot{self.token}/sendDocument"
		files = {
			"document": ("Timesheet Report.pdf", pdf, "application/pdf"),
		}
		data = {
			"chat_id": self.chat,
			"caption": "Here's the report",
		}
		try:
			response = requests.post(url, data=data, files=files)
			if response.status_code != 200:
				frappe.log_error(response.text, "Telegram PDF Send Error")
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Telegram PDF Send Failed")

	# Getting the previous working day
	def working_day(self, last_date=None):
		if not last_date:
			last_date = add_days(getdate(today()), -1)

		if is_holiday(self.holiday_list, last_date):
			return self.working_day(add_days(last_date, -1))

		return last_date

	# Getting working days
	def cnt_working_days(self, start, end):
		cnt = []
		while start <= end:
			if not is_holiday(self.holiday_list, start):
				cnt.append(str(start))
			start = add_days(start, 1)

		return cnt

	def missed_days(self, working_days):
		miss_date = {}
		for emp in self.emp_map:
			dates = ""
			for date in working_days:
				if (
					not frappe.db.exists("Timesheet", {"employee": emp, "start_date": date})
					and not is_holiday(self.holiday_list, date)
					and not frappe.db.exists(
						"Leave Application",
						{
							"employee": emp,
							"status": "Approved",
							"from_date": ["<=", date],
							"to_date": [">=", date],
						},
					)
				):
					dates += str(date)
					dates += ", "
			if dates:
				miss_date[emp] = dates[:-2]
			else:
				miss_date[emp] = "-"

		return miss_date

	# Generate pdf
	def generate_pdf(self, title, data, start, end):
		working_days = self.cnt_working_days(start, end)
		missed_date = self.missed_days(working_days)
		html = f"""<html><head><meta charset="utf-8"></head><body>
			<h1 style="text-align:center">{title} Timesheet Report</h1>
			<p>Period : {start} → {end}</p>
			<table>
				<tr>
					<th style="border:1px solid #ccc">Employee</th>
					<th style="border:1px solid #ccc">Working Days</th>
					<th style="border:1px solid #ccc">Not Filled Timesheet Date</th>
					<th style="border:1px solid #ccc">Timesheet Days</th>
					<th style="border:1px solid #ccc">Description Char Length</th>
					<th style="border:1px solid #ccc">Total Worked Hours</th>
				</tr>
			"""
		for row in data:
			html += f"""
				<tr>
					<td style="border:1px solid #ccc; text-align:center">{self.emp_map.get(row.employee)}</td>
					<td style="border:1px solid #ccc; text-align:center">{len(working_days) - (row.leave_days or 0)}</td>
					<td style="border:1px solid #ccc; text-align:center">{missed_date[row.employee]}</td>
					<td style="border:1px solid #ccc; text-align:center">{row.worked_days or 0}</td>
					<td style="border:1px solid #ccc; text-align:center">{row.des_len or 0}</td>
					<td style="border:1px solid #ccc; text-align:center">{row.total_hrs_worked or 0}</td>
				</tr>
				"""
		html += "<table></body></html>"

		return get_pdf(html)

	# Creating Summary
	def points_summary(self, title, start, end):
		data = frappe.db.sql(
			"""
			SELECT
				emp.employee,
				la.leave_days,
				COUNT(ts.name) as worked_days,
				SUM(tl.word_count) as des_len,
				SUM(ts.total_hours) as total_hrs_worked,
				CASE
					WHEN ts.name IS NOT NULL THEN SUM(
						1 +
						CASE
							WHEN tl.word_count >= %s THEN 2
							WHEN tl.word_count >= %s THEN 1
							ELSE 0.5
						END
						+ CASE
							WHEN ts.total_hours >= %s THEN 2
							ELSE 1
						END
						)
					ELSE 0
				END as total_points
			FROM `tabEmployee` emp

			LEFT JOIN (
				SELECT
					employee,
					SUM(total_leave_days) as leave_days
				FROM `tabLeave Application`
				WHERE status="Approved" AND from_date<=%s AND to_date>=%s
				GROUP BY employee
			) la ON la.employee = emp.employee

			LEFT JOIN `tabTimesheet` ts ON ts.employee = emp.employee
			AND ts.docstatus = 1
			AND ts.start_date BETWEEN %s AND %s

			LEFT JOIN (
				SELECT
					parent,
					LENGTH(GROUP_CONCAT(description SEPARATOR ' '))
					- LENGTH(REPLACE(GROUP_CONCAT(description SEPARATOR ' '), ' ', ''))
					+ 1 AS word_count
				FROM `tabTimesheet Detail`
				GROUP BY parent
			) tl ON tl.parent = ts.name

			GROUP BY emp.employee
			""",
			(self.avg_char_len, self.avg_char_len // 2, self.avg_working_hrs, start, end, start, end),
			as_dict=True,
		)

		summary = [f"{title} Points : {start} - {end}\n"]
		for row in data:
			summary.append(f"{self.emp_map.get(row.employee)} : {row.total_points} points")

		pdf = self.generate_pdf(title, data, start, end)

		return "\n".join(summary), pdf

	# Set Daily Points
	def set_daily_points(self):
		if not self.setting.daily or self.setting.disable:
			return

		last_working_day = self.working_day()

		if is_holiday(self.holiday_list):
			return None

		msg, pdf = self.points_summary("EOD", last_working_day, last_working_day)

		self.send_telegram_message(msg, pdf)

	# Set Weekly Points
	def set_weekly_points(self):
		if not self.setting.weekly or self.setting.disable:
			return

		cur = getdate(today())
		start = add_days(cur, -7 - cur.weekday())
		end = add_days(start, 5)

		msg, pdf = self.points_summary("Weekly", start, end)

		self.send_telegram_message(msg, pdf)

	# Set Monthly Points
	def set_monthly_points(self):
		if not self.setting.monthly or self.setting.disable:
			return

		end = getdate(today())
		end = end.replace(day=1)
		start = add_months(end, -1)
		end = add_days(end, -1)

		msg, pdf = self.points_summary("Monthly", start, end)

		self.send_telegram_message(msg, pdf)


def set_points():
	point = Points()
	point.set_daily_points()

	date = getdate(today())
	if date.weekday() == 0:
		point.set_weekly_points()
	if date.day == 1:
		point.set_monthly_points()


def redis_queue():
	frappe.enqueue(method="timesheetpointingsystem.points.set_points", queue="long")
