import frappe
from frappe.utils import today, getdate, add_days, add_months
import requests

# Sending Messages on Telegram Group Bot
def send_telegram_message(msg) :
    setting = frappe.get_doc("Points Configuration")
    token = setting.token
    chat = setting.chat

    if  not token or not chat :
        frappe.log_error("Missing Telegram token/chat_id", "Telegram Config Error")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": msg, "parse_mode": "Markdown"}

    try :
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            frappe.log_error(response.text, "Telegram Message Error")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Telegram Message Failed")

# Getting the previous working day
def working_day() :

    cur_date = getdate(today())
    if frappe.get_value("Holiday", {"holiday_date" : cur_date, "parent" : "Yearly Holidays"}) : return None
    last_working_day = None

    for i in range(1,8) :
        check_date = add_days(cur_date, -i)

        if check_date.weekday() in (5,6) or frappe.get_value("Holiday", {"holiday_date" : check_date, "parent" : "Yearly Holidays"}) :
            continue

        last_working_day = check_date
        break
    
    return last_working_day

# Getting the starting working day of the previous week
def starting_working_day_for_last_week() :
    cur_date = getdate(today())

    if cur_date.weekday() not in (5,6) :
        cur_date = add_days(cur_date, -7)
    
    week_day = add_days(cur_date, -cur_date.weekday())
    for i in range(7) :
        check_date = add_days(week_day, i)

        if check_date.weekday() in (5,6) or frappe.get_value("Holiday", {"holiday_date" : check_date, "parent" : "Yearly Holidays"}) :
            continue
        else :
            break
    
    return week_day

# Getting the last working day of thr previous week
def ending_working_day_for_last_week(start) :
    end = start
    cur = start
    for i in range(4) :
        cur = add_days(cur, 1)
        if cur.weekday() in (5,6) :
            return end
        
        if frappe.get_value("Holiday", {"holiday_date" : cur, "parent" : "Yearly Holidays"}) :
            continue
        end = cur
    
    return end

# Calculate Points for Timesheet
def cal_points(timesheet, setting) :
    points = 1
    
    total_hrs = timesheet.total_hours
    if total_hrs >= setting.avg_working_hrs : points += 2
    else : points += 1

    des = []
    for tl in timesheet.time_logs :
        if tl.description : des.extend(tl.description.split(" "))
    
    if len(des) >= setting.avg_char_len : points += 2
    elif len(des) >= setting.avg_char_len//2 : points += 1
    else : points += .5
    return points

# Creating Summary
def points_summary(title, start, end) :
    employees = frappe.get_all("Employee", fields=["name","employee_name"])
    summary = [f"{title} Points : {start} - {end}\n"]
    setting = frappe.get_doc("Points Configuration")
    for emp in employees :
        timesheets = frappe.get_all("Timesheet", filters={"employee":emp.name, "start_date":["between", [start, end]]}, pluck="name")

        points = 0
        for ts in timesheets :
            timesheet = frappe.get_doc("Timesheet", ts)
            points += cal_points(timesheet, setting)

        summary.append(f"{emp.employee_name} : {points} points")

    return "\n".join(summary)

# Setting Daily Points
def set_daily_points() :
    last_working_day = working_day()
    if last_working_day is None : return

    msg = points_summary("EOD", last_working_day, last_working_day)

    send_telegram_message(msg)

# Set Weekly Points
def set_weekly_points() :
    start = starting_working_day_for_last_week()
    end = ending_working_day_for_last_week(start)

    msg = points_summary("Weekly", start, end)

    send_telegram_message(msg)

# Set Monthly Points
def set_monthly_points() :
    end = getdate(today())
    end = end.replace(day=1)
    start = add_months(end, -1)
    end = add_days(end, -1)

    msg = points_summary("Monthly", start, end)

    send_telegram_message(msg)