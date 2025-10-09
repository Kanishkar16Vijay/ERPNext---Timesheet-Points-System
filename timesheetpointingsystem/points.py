import frappe
import requests
from frappe.utils import add_days, add_months, getdate, today


class Points:
	def __init__(self):
		self.setting = frappe.get_doc("Points Configuration")
		self.token = self.setting.get_password("token")
		self.chat = self.setting.chat
		self.avg_working_hrs = self.setting.avg_working_hrs
		self.avg_char_len = self.setting.avg_char_len

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
	def working_day(self):
		cur_date = getdate(today())
		if frappe.get_value("Holiday", {"holiday_date": cur_date, "parent": "Yearly Holidays"}):
			return None
		last_working_day = None

		for i in range(1, 8):
			check_date = add_days(cur_date, -i)

			if check_date.weekday() in (5, 6) or frappe.get_value(
				"Holiday", {"holiday_date": check_date, "parent": "Yearly Holidays"}
			):
				continue

			last_working_day = check_date
			break

		return last_working_day

	# Getting the starting working day of the previous week
	def starting_working_day_for_last_week(self):
		cur_date = getdate(today())

		if cur_date.weekday() not in (5, 6):
			cur_date = add_days(cur_date, -7)

		week_day = add_days(cur_date, -cur_date.weekday())
		for i in range(7):
			check_date = add_days(week_day, i)

			if check_date.weekday() in (5, 6) or frappe.get_value(
				"Holiday", {"holiday_date": check_date, "parent": "Yearly Holidays"}
			):
				continue
			else:
				break

		return week_day

	# Getting the last working day of thr previous week
	def ending_working_day_for_last_week(self, start):
		end = start
		cur = start
		for _i in range(4):
			cur = add_days(cur, 1)
			if cur.weekday() in (5, 6):
				return end

			if frappe.get_value("Holiday", {"holiday_date": cur, "parent": "Yearly Holidays"}):
				continue
			end = cur

		return end

	# Calculate Points for Timesheet
	def cal_points(self, timesheet, setting):
		points_details = setting.criteria_and_pts

		points = 0
		for pd in points_details:
			if pd.criteria == "Timesheet":
				points += pd.points  # For submitting timesheet

			elif pd.criteria == "Description":  # Counting the length of the description
				des = []
				for tl in timesheet.time_logs:
					if tl.description:
						des.extend(tl.description.split(" "))

				if len(des) >= setting.avg_char_len:
					points += pd.points
				elif len(des) >= setting.avg_char_len // 2:
					points += pd.points / 2
				else:
					points += pd.points / 4

			elif pd.criteria == "Working Hours":  # Calculating the working hours
				total_hrs = timesheet.total_hours
				if total_hrs >= setting.avg_working_hrs:
					points += pd.points
				else:
					points += pd.points / 2

			elif pd.criteria == "Timesheet Creation":  # Getting the timesheet creation time
				if getdate(timesheet.modified) == timesheet.start_date:
					points += pd.points

		return round(points, 1)

	# Creating Summary
	def points_summary(self, title, start, end):
		employees = frappe.get_all("Employee", fields=["name", "employee_name"])
		summary = [f"{title} Points : {start} - {end}\n"]
		for emp in employees:
			timesheets = frappe.get_all(
				"Timesheet",
				filters={"employee": emp.name, "docstatus": 1, "start_date": ["between", [start, end]]},
				pluck="name",
			)

			points = 0
			for ts in timesheets:
				timesheet = frappe.get_doc("Timesheet", ts)
				points += self.cal_points(timesheet, self.setting)

			summary.append(f"{emp.employee_name} : {points} points")

		return "\n".join(summary)

	# Set Daily Points
	def set_daily_points(self):
		if not self.setting.daily or self.setting.disable:
			return

		last_working_day = self.working_day()
		if last_working_day is None:
			return

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
	if getdate(today()).weekday() == 0:
		point.set_weekly_points()
	if getdate(today()).day == 1:
		point.set_monthly_points()
