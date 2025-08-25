
Attendance Late/Early Penalty (Odoo 18)
======================================

Features
--------
- Configurable allowed occurrences per month (Settings > Attendance).
- Choose the leave type for the penalty.
- Detects late check-in or early check-out **based on each employee's working schedule**.
- On the (allowed_count + 1)-th late/early in the month, automatically creates a **half-day** leave for that day.
- AM/PM half-day is chosen automatically:
  - Late check-in => AM half-day
  - Early check-out => PM half-day

Install
-------
1. Put this folder in your addons path.
2. Update apps list and install *Attendance Late/Early Penalty*.
3. In Settings, search for "Attendance Late/Early Penalty" and set:
   - Allowed Late/Early Count
   - Penalty Leave Type

Notes
-----
- The module avoids creating duplicate penalty leaves for the same day.
- Timezone is taken from the employee/user to compare with the working hours.
