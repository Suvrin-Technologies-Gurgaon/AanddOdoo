# -*- coding: utf-8 -*-
{
    'name': 'Open HRMS Loan Management',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage Employee Loan Requests',
    'description': """This module facilitates the creation and management of 
     employee loan requests. The loan amount is automatically deducted from the 
     salary""",
    'author': "suvrin technologies pvt ltd",
    'company': 'suvrin technologies pvt ltd',
    'maintainer': 'suvrin technologies pvt ltd',
    'depends': ['hr', 'account', 'sh_hr_payroll'],
    'data': [
        'security/hr_loan_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/hr_salary_rule_demo.xml',
        'data/hr_rule_input_demo.xml',
        'views/hr_loan_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_employee_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
