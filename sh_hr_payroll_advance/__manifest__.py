# -*- coding:utf-8 -*-
{
    "name": "HR Payroll - Advance Flow",
    "license": "OPL-1",
    "category": "Payroll",
    "summary": "Payroll System Human Resource Payroll HR Payroll Employee Payroll Records Salary Rules Salary Structure Print Payslip Journal Entry Payslip Journal Item Payslip Accounting Employee Salary Management Employee Payslip Management Odoo",
    "description": """This module helps to manage the payroll of your organization. You can manage employee contracts with a salary structure. You can create an employee payslip and compute employee salary with salary structures & salary rules. You can generate all payslips using payslip batches.""",
    "version": "18.0.0.0",
    "depends": [
        "hr",
        "hr_holidays",
        "sh_hr_payroll"
    ],
    "data": [
        "data/cron_jobs.xml",
    ],
    "application": True,
    "auto_install": False,
    "installable": True,
}
