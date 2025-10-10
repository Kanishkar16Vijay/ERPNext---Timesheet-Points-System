import frappe
import requests
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday
from frappe.utils import add_days, add_months, getdate, today


class Points:
	def __init__(self):
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
	def send_telegram_message(self, msg):
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

	# Getting the previous working day
	def working_day(self, last_date=None):
		if not last_date:
			last_date = add_days(getdate(today()), -1)

		if is_holiday(self.holiday_list, last_date):
			return self.working_day(add_days(last_date, -1))

		return last_date

	# Getting the starting working day of the previous week
	def starting_working_day_for_last_week(self):
		cur_date = getdate(today())

		if cur_date.weekday() not in (5, 6):
			cur_date = add_days(cur_date, -7)

		week_day = add_days(cur_date, -cur_date.weekday())
		for i in range(7):
			check_date = add_days(week_day, i)

			if not is_holiday(self.holiday_list, check_date):
				return week_day

		return week_day

	# Getting the last working day of thr previous week
	def ending_working_day_for_last_week(self, start):
		end = start
		cur = start
		for _i in range(5):
			cur = add_days(cur, 1)
			if cur.weekday() in (5, 6):
				break

			if is_holiday(self.holiday_list, cur):
				continue
			end = cur

		return end

	# Creating Summary
	def points_summary(self, title, start, end):
		data = frappe.db.sql(
			"""
			SELECT
				ts.employee,
				SUM(
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
					) as total_points
			FROM `tabTimesheet` ts
			LEFT JOIN(
				SELECT
					parent,
					LENGTH(GROUP_CONCAT(description SEPARATOR ' ')) - LENGTH(REPLACE(GROUP_CONCAT(description SEPARATOR ' '), ' ', '')) + 1 AS word_count
				FROM `tabTimesheet Detail`
				GROUP BY parent ) tl ON tl.parent=ts.name
			WHERE ts.docstatus=1 AND ts.start_date BETWEEN %s AND %s
			GROUP BY ts.employee
		""",
			(self.avg_char_len, self.avg_char_len // 2, self.avg_working_hrs, start, end),
			as_dict=True,
		)

		summary = [f"{title} Points : {start} - {end}\n"]
		for points in data:
			summary.append(
				f"{frappe.get_value('Employee', points.employee, 'employee_name')} : {points.total_points} points"
			)

		return "\n".join(summary)

	# Set Daily Points
	def set_daily_points(self):
		if not self.setting.daily or self.setting.disable:
			return

		last_working_day = self.working_day()

		if is_holiday(self.holiday_list):
			return None

		msg = self.points_summary("EOD", last_working_day, last_working_day)

		self.send_telegram_message(msg)

	# Set Weekly Points
	def set_weekly_points(self):
		if not self.setting.weekly or self.setting.disable:
			return

		start = self.starting_working_day_for_last_week()
		end = self.ending_working_day_for_last_week(start)

		msg = self.points_summary("Weekly", start, end)

		self.send_telegram_message(msg)

	# Set Monthly Points
	def set_monthly_points(self):
		if not self.setting.monthly or self.setting.disable:
			return

		end = getdate(today())
		end = end.replace(day=1)
		start = add_months(end, -1)
		end = add_days(end, -1)

		msg = self.points_summary("Monthly", start, end)

		self.send_telegram_message(msg)


def set_points():
	point = Points()
	point.set_daily_points()

	date = getdate(today())
	if date.weekday() == 0:
		point.set_weekly_points()
	if date.day == 1:
		point.set_monthly_points()
