# -*- coding: utf-8 -*-
{
    'name': 'Open HRMS Loan Accounting',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Open HRMS Loan Accounting',
    'description': """Create accounting entries for loan requests.""",
    'author': "suvrin technologies pvt ltd",
    'company': 'suvrin technologies pvt ltd',
    'maintainer': 'suvrin technologies pvt ltd',
    'depends': [
        'sh_hr_payroll', 'hr', 'account', 'ohrms_loan',
    ],
    'data': [
        'security/ohrms_loan_accounting_security.xml',
        'views/res_config_settings_views.xml',
        'views/hr_loan_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
