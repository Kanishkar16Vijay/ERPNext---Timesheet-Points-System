import frappe
from frappe.utils import today, getdate, add_days, add_months
import requests
import os
from dotenv import load_dotenv

def working_day() : # Child function of set_daily_points

    cur_date = getdate(today())
    if frappe.get_value("Holiday", {"holiday_date" : cur_date, "parent" : "Yearly Holidays"}) : return
    last_working_day = None

    for i in range(1,8) :
        check_date = add_days(cur_date, -i)

        if check_date.weekday() in (5,6) or frappe.get_value("Holiday", {"holiday_date" : check_date, "parent" : "Yearly Holidays"}) :
            continue

        last_working_day = check_date
        break
    
    return last_working_day

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

def no_of_working_days_in_week(date) :
    cnt = 1
    for i in range(4) :
        date = add_days(date, 1)
        if date.weekday() in (5,6) or frappe.get_value("Holiday", {"holiday_date" : date, "parent" : "Yearly Holiday"}) :
            continue

        cnt += 1
    
    return cnt

def total_working_days_in_month() :
    cur = getdate(today())
    start_date = add_months(cur, -1)
    start_date = start_date.replace(day=1)
    end_date = cur.replace(day=1)
    end_date = add_days(end_date, -1)

    count = 0
    while start_date<=end_date :
        if start_date.weekday() in (5,6) or frappe.get_value("Holiday", {"holiday_date" : start_date, "parent" : "Yearly Holiday"}) :
            start_date = add_days(start_date, 1)
            continue
        
        count += 1
        start_date = add_days(start_date, 1)
    
    return count

def cal_daily(timesheet, setting) :
    points = 1
    
    total_hrs = timesheet.total_hours
    if total_hrs >= setting.avg_working_hrs : points += 2
    else : points += 1

    description = []
    for tl in timesheet.time_logs :
        if tl.description : description += tl.description.split(" ")
    
    if len(description) < setting.avg_char_len//4 : points += 0.5
    elif len(description) < setting.avg_char_len//2 : points += 1
    else : points += 2

    return points

# Sending Messages on Telegram Group Bot
def send_telegram_message(msg) :
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": msg, "parse_mode": "Markdown"}

    try :
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            frappe.log_error(response.text, "Telegram Message Error")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Telegram Message Failed")

# Setting Daily Points
def set_daily_points() :

    last_working_day = working_day()
    if last_working_day is None : return

    summary = [f"*EOD Points* ({last_working_day})\n"]
    setting = frappe.get_doc("Points Configuration")
    timesheets = frappe.get_all("Timesheet", filters = {"start_date" : last_working_day}, pluck = "name")

    for ts in timesheets :
        points = 1
        timesheet = frappe.get_doc("Timesheet", ts)
        employee = timesheet.employee
        
        total_hrs = timesheet.total_hours
        if total_hrs >= setting.avg_working_hrs : points += 2
        else : points += 1

        description = []
        for tl in timesheet.time_logs :
            if tl.description : description += tl.description.split(" ")
        
        if len(description) < setting.avg_char_len//4 : points += 0.5
        elif len(description) < setting.avg_char_len//2 : points += 1
        else : points += 2

        summary.append(f"{timesheet.employee_name} : {points} points")

    msg = "\n".join(summary)
    send_telegram_message(msg)

# Set Weekly Points
def set_weekly_points() :
    employees = frappe.get_all("Employee", pluck = "name")
    setting = frappe.get_doc("Points Configuration")
    summary = [f"*Weekly Points*\n"]

    for emp in employees :
        date = starting_working_day_for_last_week()
        timesheets = frappe.get_all("Timesheet", filters = {"employee" : emp, "start_date" : [">=",date]})
        # no_working_days = no_of_working_days_in_week(date)

        if not timesheets : continue

        points = 0
        # if len(timesheets) >= 5 : points += 1

        # tot_hrs = 0
        # des = []
        for ts in timesheets :
            timesheet = frappe.get_doc("Timesheet", ts)
            points += cal_daily(timesheet, setting)
        #     tot_hrs += timesheet.total_hours
        #     for log in timesheet.time_logs :
        #         if log.description : des += log.description.split(" ")
        
        # if tot_hrs >= setting.avg_working_hrs * no_working_days : points += 2
        # elif tot_hrs >= (setting.avg_working_hrs * no_working_days)//2 : points += 1
        # else : points += 0.5

        # if len(des) >= setting.avg_char_len * no_working_days : points += 2
        # elif len(des) >= (setting.avg_char_len * no_working_days)//2 : points += 1
        # else : points += 0.5

        empl = frappe.get_doc("Employee", emp)
        summary.append(f"{empl.employee_name} : {points} points")
    
    msg = "\n".join(summary)
    send_telegram_message(msg)

# Set Monthly Points
def set_monthly_points() :
    employees = frappe.get_all("Employee", pluck = "name")
    summary = [f"*Monthly Points*\n"]

    cur = getdate(today())
    last_month = add_months(cur, -1)
    last_month = last_month.replace(day=1)
    cur = cur.replace(day=1)
    cur = add_days(cur, -1)
    # working_days = total_working_days_in_month()

    for emp in employees :
        setting = frappe.get_doc("Points Configuration")
        timesheets = frappe.get_all("Timesheet", filters={"employee" : emp, "start_date" : ["between",[last_month, cur]]})
    
        if not timesheets : continue

        points = 0
        # if len(timesheets) >= working_days : points += 1
        
        # tot_hrs = 0
        # des = []
        for ts in timesheets :
            timesheet = frappe.get_doc("Timesheet", ts)
            points += cal_daily(timesheet, setting)
        #     tot_hrs += timesheet.total_hours
        #     for log in timesheet.time_logs :
        #         if log.description : des += log.description.split(" ")
            
        # if tot_hrs >= setting.avg_working_hrs * working_days : points += 2
        # elif tot_hrs >= (setting.avg_working_hrs * working_days)//2 : points += 1
        # else : points += 0.5

        # if len(des) >= setting.avg_char_len * working_days : points += 2
        # elif len(des) >= (setting.avg_char_len * working_days)//2 : points += 1
        # else : points += 0.5

        employee = frappe.get_doc("Employee", emp)
        summary += [f"{employee.employee_name} : {points} points"]
    
    msg = "\n".join(summary)
    send_telegram_message(msg)