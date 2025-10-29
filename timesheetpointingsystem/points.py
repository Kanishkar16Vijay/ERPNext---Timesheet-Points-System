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

		session = requests.Session()
		url = f"https://api.telegram.org/bot{self.token}"

		try:
			msg_response = session.post(
				f"{url}/sendMessage",
				data={
					"chat_id": self.chat,
					"text": msg,
					"parse_mode": "Markdown",
				},
			)
			msg_response.raise_for_status()
			message_id = msg_response.json().get("result", {}).get("message_id")

			files = {"document": ("Timesheet Report.pdf", pdf, "application/pdf")}
			data = {
				"chat_id": self.chat,
				"caption": "Timesheet Report",
			}
			if message_id:
				data["reply_to_message_id"] = message_id

			file_response = session.post(f"{url}/sendDocument", data=data, files=files)
			file_response.raise_for_status()

		except Exception as e:
			frappe.log_error(f"{e!s}\n{frappe.get_traceback()}", "Telegram Send Error")

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

	# Getting missing dates for timesheet
	def missed_days(self, working_days):
		miss_date = {}
		timesheet_entries = frappe.get_all(
			"Timesheet",
			filters={"start_date": ["in", working_days]},
			fields=["employee", "start_date"],
			as_list=True,
		)
		leave_entries = frappe.get_all(
			"Leave Application",
			filters={
				"status": "Approved",
				"from_date": ["<=", max(working_days)],
				"to_date": [">=", min(working_days)],
			},
			fields=["employee", "from_date", "to_date"],
		)
		timesheet_set = {(emp, str(date)) for emp, date in timesheet_entries}
		for emp in self.emp_map:
			dates = []
			for date in working_days:
				if (
					(emp, str(date)) not in timesheet_set
					and not any(
						l["from_date"] <= getdate(date) <= l["to_date"]
						for l in leave_entries
						if l["employee"] == emp
					)
					and not is_holiday(self.holiday_list, date)
				):
					dates.append(str(date))

			miss_date[emp] = ", ".join(dates) if dates else "-"

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
					<td style="border:1px solid #ccc; text-align:center">{len(working_days) - row.leave_days}</td>
					<td style="border:1px solid #ccc; text-align:center">{missed_date[row.employee]}</td>
					<td style="border:1px solid #ccc; text-align:center">{row.worked_days}</td>
					<td style="border:1px solid #ccc; text-align:center">{row.des_len}</td>
					<td style="border:1px solid #ccc; text-align:center">{row.total_hrs_worked}</td>
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
				COALESCE(la.leave_days, 0) AS leave_days,
				COUNT(ts.name) AS worked_days,
				COALESCE(SUM(tl.word_count), 0) AS des_len,
				COALESCE(SUM(ts.total_hours), 0) AS total_hrs_worked,
				CASE
					WHEN ts.name IS NOT NULL THEN SUM(
						1 +
						CASE
							WHEN tl.word_count >= %(avg_char_len)s THEN 2
							WHEN tl.word_count >= %(half_char_len)s THEN 1
							ELSE 0.5
						END
						+ CASE
							WHEN ts.total_hours >= %(avg_wrk_hrs)s THEN 2
							ELSE 1
						END
						)
					ELSE 0
				END as total_points
			FROM `tabEmployee` emp

			LEFT JOIN (
				SELECT
					employee,
					SUM(
						DATEDIFF(
							LEAST(to_date, %(end)s),
							GREATEST(from_date, %(start)s)
						)
						+ 1
					) as leave_days
				FROM `tabLeave Application`
				WHERE status="Approved" AND from_date<=%(end)s AND to_date>=%(start)s
				GROUP BY employee
			) la ON la.employee = emp.employee

			LEFT JOIN `tabTimesheet` ts ON ts.employee = emp.employee
			AND ts.docstatus = 1
			AND ts.start_date BETWEEN %(start)s AND %(end)s

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
			{
				"avg_char_len": self.avg_char_len,
				"half_char_len": self.avg_char_len // 2,
				"avg_wrk_hrs": self.avg_working_hrs,
				"start": start,
				"end": end,
			},
			as_dict=True,
		)

		summary = [f"{title} Points : {start} - {end}\n"]
		for row in data:
			summary.append(f"{self.emp_map.get(row.employee)} : {row.total_points} points")

		pdf = self.generate_pdf(title, data, start, end)

		return "\n".join(summary), pdf

	# Set Daily Points
	def set_daily_points(self):
		last_working_day = self.working_day()

		if is_holiday(self.holiday_list):
			return None

		msg, pdf = self.points_summary("EOD", last_working_day, last_working_day)

		self.send_telegram_message(msg, pdf)

	# Set Weekly Points
	def set_weekly_points(self):
		cur = getdate(today())
		start = add_days(cur, -7 - cur.weekday())
		end = add_days(start, 5)

		msg, pdf = self.points_summary("Weekly", start, end)

		self.send_telegram_message(msg, pdf)

	# Set Monthly Points
	def set_monthly_points(self):
		end = getdate(today())
		end = end.replace(day=1)
		start = add_months(end, -1)
		end = add_days(end, -1)

		msg, pdf = self.points_summary("Monthly", start, end)

		self.send_telegram_message(msg, pdf)


def set_points():
	point = Points()
	if point.setting.disable:
		return

	if point.setting.daily:
		point.set_daily_points()

	date = getdate(today())
	if date.weekday() == 0 and point.setting.weekly:
		point.set_weekly_points()

	if date.day == 1 and point.setting.monthly:
		point.set_monthly_points()


def redis_queue():
	frappe.enqueue(method="timesheetpointingsystem.points.set_points", queue="long")
