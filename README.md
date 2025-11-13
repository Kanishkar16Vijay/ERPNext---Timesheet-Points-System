## Timesheet Pointing System

Give point for timesheet by daily, weekly, and monthly

### Points Configuration
Points configuration is a single doc and it has following fields

1. **Avg Working Hours :** This field defines the average number of working hours expected from an employee on a daily basis. It is used to evaluate whether the employee has completed sufficient work hours each day when calculating points.

2. **Avg Character Lenght in Description :** This sets an average or minimum standard length for the description field in the timesheet. It helps ensure employees provide detailed and meaningful descriptions of their daily tasks instead of short or incomplete entries.

3. **Telegram Bot Token :** This field stores the token ID obtained from the ***BotFather Bot*** in Telegram. The token allows the system to connect and send automated notifications or messages to employees through the Telegram bot.

4. **Chat ID :** The Chat ID represents the unique conversation area in Telegram where messages will be sent. It ensures that updates, alerts, or summaries are delivered to the correct chat or group.

5. **Daily :** When this option is checked, the system calculates timesheet points on a daily basis, based on factors like work hours, description quality, and task completion.

6. **Weeky :** If this option is selected, the system compiles and calculates points for employees weekly, summarizing their total hours, consistency, and performance for that week.

7. **Monthly :** When enabled, this option triggers the calculation of points monthly, providing an overall performance score for the employee over the entire month.

8. **Holiday List :** This field is linked to the company’s official holiday list. It helps the system exclude holidays from point calculations to ensure fairness in attendance and work-hour evaluations.

9. **Rank by :** This defines the ranking criteria, allowing the system to rank employees based on their total points or performance metrics, highlighting the top performers within a given period.

10. **Employees to Ignore :** This is a list of employees who are active in the system but are exempted from timesheet evaluations or point calculations (for example, senior managers, interns, or consultants).

11. **Calculate Points for custom dates :** This is an actionable button that opens a dialog box with “From Date” and “To Date” fields. It allows the user to manually calculate timesheet points for a custom date range, outside of the regular daily, weekly, or monthly schedule.
