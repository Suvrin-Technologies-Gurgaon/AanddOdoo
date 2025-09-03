{
    'name': 'Advanced Leave Flow',
    'version': '18.0.0.0',
    'category': 'HR',
    'summary': 'Handles earned leave carry forward, priority deduction, and dynamic comp-off expiry with cron jobs',
    'depends': ['hr', 'hr_holidays', 'sh_hr_payroll'],
    'data': [
        'data/cron_jobs.xml',
        'views/hr_leave.xml',
        'menu/menu.xml'
    ],
    'installable': True,
    'auto_install': False,
}