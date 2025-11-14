import frappe
import requests
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday
from frappe.utils import add_days, add_months, getdate, today
from frappe.utils.pdf import get_pdf


class Points:
	def __init__(self):
		self.emp_map = dict(
			frappe.get_all(
				"Employee", filters={"status": "Active"}, fields=["name", "employee_name"], as_list=True
			)
		)
		self.setting = frappe.get_doc("Points Configuration")
		self.token = self.setting.get_password("token")
		self.chat = self.setting.chat
		self.thread = self.setting.thread_id
		self.avg_working_hrs = self.setting.avg_working_hrs
		self.avg_char_len = self.setting.avg_char_len
		self.holiday_list = self.setting.holiday_list or frappe.get_value(
			"Company", "Aerele Technologies", "default_holiday_list"
		)
		self.rank = self.setting.rank
		__employee = tuple(
			emp[0] for emp in frappe.db.sql("SELECT employee FROM `tabEmployee List`", as_list=True)
		)
		self.employees_to_ignore = ", ".join(f"'{x}'" for x in __employee) or "'NO_EMPLOYEE'"

	# Sending Messages on Telegram Group Bot
	def send_telegram_message(self, msg, pdf):
		if not self.token or not self.chat:
			frappe.log_error("Telegram Config Error", "Missing Telegram token/chat_id")
			return

		session = requests.Session()
		url = f"https://api.telegram.org/bot{self.token}"

		try:
			payload = {
				"chat_id": self.chat,
				"text": msg,
				"parse_mode": "Markdown",
			}
			if self.thread:
				payload["message_thread_id"] = self.thread

			msg_response = session.post(f"{url}/sendMessage", data=payload)
			msg_response.raise_for_status()

			message_id = msg_response.json().get("result", {}).get("message_id")

			files = {"document": ("Timesheet Report.pdf", pdf, "application/pdf")}
			payload = {
				"chat_id": self.chat,
				"caption": "Timesheet Report",
			}
			if self.thread:
				payload["message_thread_id"] = self.thread

			if message_id:
				payload["reply_to_message_id"] = message_id

			file_response = session.post(f"{url}/sendDocument", data=payload, files=files)
			file_response.raise_for_status()

		except Exception as e:
			frappe.log_error("Telegram Send Error", f"{e!s}\n{frappe.get_traceback()}")

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
		if not working_days:
			return {}

		date_cte = " UNION ALL ".join([f"SELECT DATE('{d}') AS work_date" for d in working_days])

		query = f"""
			WITH working_dates AS (
				{date_cte}
			),
			employee_dates AS (
				SELECT
					e.name AS employee,
					w.work_date
				FROM `tabEmployee` e
				JOIN working_dates w ON 1=1
				WHERE e.status="Active"
				AND e.employee NOT IN ({self.employees_to_ignore})
			)
			SELECT
				epd.employee AS employee,
				GROUP_CONCAT(DATE_FORMAT(epd.work_date, '%Y-%m-%d') ORDER BY epd.work_date) AS missed_dates
			FROM employee_dates epd

			LEFT JOIN `tabTimesheet` ts
				ON ts.employee = epd.employee
				AND ts.docstatus = 1
				AND DATE(ts.start_date) = epd.work_date

			LEFT JOIN `tabLeave Application` la
				ON la.employee = epd.employee
				AND la.status = 'Approved'
				AND epd.work_date BETWEEN la.from_date AND la.to_date

			WHERE ts.name IS NULL
			AND la.name IS NULL
			GROUP BY epd.employee;
		"""

		results = frappe.db.sql(query, as_dict=True)
		miss_date = {row["employee"]: row["missed_dates"] or "-" for row in results}

		for emp in self.emp_map:
			if emp not in miss_date:
				miss_date[emp] = "-"

		return miss_date

	# Creating Summary
	def points_summary(self, title, start, end):
		data = frappe.db.sql(
			f"""
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
							WHEN tl.word_count >= {self.avg_char_len} THEN 2
							WHEN tl.word_count >= {self.avg_char_len//2} THEN 1
							WHEN tl.word_count >= 1 THEN 0.5
							ELSE 0
						END
						+ CASE
							WHEN ts.total_hours >= {self.avg_working_hrs} THEN 2
							WHEN ts.total_hours >= {self.avg_working_hrs//2} THEN 1
							WHEN ts.total_hours >= 1.5 THEN 0.5
							ELSE 0
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
							LEAST(to_date, '{end}'),
							GREATEST(from_date, '{start}')
						)
						+ 1
					) as leave_days
				FROM `tabLeave Application`
				WHERE status="Approved" AND from_date<='{end}' AND to_date>='{start}'
				GROUP BY employee
			) la ON la.employee = emp.employee

			LEFT JOIN `tabTimesheet` ts ON ts.employee = emp.employee
			AND ts.docstatus = 1
			AND ts.start_date BETWEEN '{start}' AND '{end}'

			LEFT JOIN (
				SELECT
					parent,
					LENGTH(GROUP_CONCAT(description SEPARATOR ' '))
					- LENGTH(REPLACE(GROUP_CONCAT(description SEPARATOR ' '), ' ', ''))
					+ 1 AS word_count
				FROM `tabTimesheet Detail`
				GROUP BY parent
			) tl ON tl.parent = ts.name

			WHERE emp.status="Active"
			AND emp.employee NOT IN ({self.employees_to_ignore})
			GROUP BY emp.employee
			ORDER BY total_points DESC
			""",
			as_dict=True,
		)

		summary = [f"{title} Points : {start} - {end}\n"]

		working_days = self.cnt_working_days(start, end)
		missed_date = self.missed_days(working_days)
		no_wrk_days = len(working_days)
		style = """
			<style>
				body { font-family: Arial, sans-serif; font-size: 12px; }
				h1 { text-align: center; color: #333; }
				p { text-align: center; }
				table { width: 100%; border-collapse: collapse; margin-top: 10px; }
				th, td { border: 1px solid #ccc; padding: 6px; text-align: center; }
			</style>
			"""

		html = f"""<html><head>{style}</head><body>
			<h1 style="text-align:center">{title} Timesheet Report</h1>
			<p>Period : {start} → {end}</p>
			<table>
				<tr>
					<th>Employee</th>
					<th>Working Days</th>
					<th>Not Filled Timesheet Date</th>
					<th>Timesheet Days</th>
					<th>Description Char Length</th>
					<th>Total Worked Hours</th>
				</tr>
			"""
		rank_cnt = 0
		for row in data:
			html += f"""
				<tr>
					<td>{self.emp_map.get(row.employee)}</td>
					<td>{no_wrk_days - row.leave_days}</td>
					<td>{missed_date[row.employee]}</td>
					<td>{row.worked_days}</td>
					<td>{row.des_len}</td>
					<td>{row.total_hrs_worked}</td>
				</tr>
				"""
			if rank_cnt < self.rank:
				summary.append(f"{self.emp_map.get(row.employee)} : {row.total_points} points")
				rank_cnt += 1
		if title != "Custom":
			summary.append(f"#{title}")

		html += "<table></body></html>"

		pdf = get_pdf(html)

		return "\n".join(summary), pdf

	# Set Daily Points
	def set_daily_points(self):
		last_working_day = self.working_day()

		msg, pdf = self.points_summary("Daily", last_working_day, last_working_day)

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

	# Set Points for Custom dates
	def set_custom_points(self, start, end):
		msg, pdf = self.points_summary("Custom", start, end)
		self.send_telegram_message(msg, pdf)


def set_points(start=None, end=None):
	point = Points()
	if not point.holiday_list:
		frappe.log_error("Holiday List Error", "Holiday List not set in Points Configuration or Company")
		return

	if start and end:
		point.set_custom_points(start, end)
		return

	if point.setting.disable:
		return

	if point.setting.daily and not is_holiday(point.holiday_list):
		point.set_daily_points()

	date = getdate(today())
	if date.weekday() == 0 and point.setting.weekly:
		point.set_weekly_points()

	if date.day == 1 and point.setting.monthly:
		point.set_monthly_points()


@frappe.whitelist()
def redis_queue(start=None, end=None):
	frappe.enqueue(method="timesheetpointingsystem.points.set_points", queue="long", start=start, end=end)
