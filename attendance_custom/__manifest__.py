# -- coding: utf-8 --
{
    "name": "Attendance Custom",
    "summary": "Auto create the attendance for employee",
    "version": "1.2.1",
    "author": "KPGTC",
    "website": "",
    "support": "",
    "depends": ['hr_attendance','mail'],
    "data": [
        'data/auto_attendance_create.xml',
        'security/ir.model.access.csv',
        'views/emp_out_office_schedule.xml',
    ],
    "license": "OPL-1",
}
