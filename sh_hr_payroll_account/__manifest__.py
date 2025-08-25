# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

{
    "name": "Payroll Accounting - Community Edition",
    "author": "Softhealer Technologies,Odoo SA",
    "license": "OPL-1",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Accounting",
    "summary": "Payroll System,Human Resource Payroll,HR Payroll,Employee Payroll Records,Salary Rules,Salary Structure,Print Payslip,Payslip Journal Entry,Payslip Journal Item,Payslip Accounting,Employee Salary Management Odoo",
    "description": """This module helps to manage the payroll of your organization. You can manage employee contracts with a salary structure. You can create an employee payslip and compute employee salary with salary structures & salary rules. You can generate all payslips using payslip batches. It generates journal entries for payslips.""",
    "version": "0.0.1",
    "depends": ["sh_hr_payroll", "account"],
    "data": ["views/hr_payroll_account_views.xml"],
    "demo": ["data/hr_payroll_account_demo.xml"],
    "application": True,
    "auto_install": False,
    "installable": True,
    "images": [
        "static/description/background.png",
    ],
    "price": 10,
    "currency": "EUR",
}
