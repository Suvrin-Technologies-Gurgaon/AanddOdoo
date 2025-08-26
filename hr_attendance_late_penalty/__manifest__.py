# -*- coding: utf-8 -*-
{
    "name": "Attendance Late/Early Penalty (Configurable)",
    "version": "18.0.1.0.0",
    "summary": "Auto half-day leave after configurable late/early occurrences; checks employee's working hours.",
    "author": "ChatGPT",
    "license": "LGPL-3",
    "category": "Human Resources/Attendance",
    "depends": ["hr_attendance", "hr_holidays", "hr"],
    "data": [
        'security/ir.model.access.csv',
        "data/cron.xml",
        "views/hr_leave_views.xml",
        "views/res_config_settings_view.xml",
        "views/hr_attendance_views.xml",
        "views/hr_client_visit.xml"
    ],
    "installable": True,
    "application": False,
}
