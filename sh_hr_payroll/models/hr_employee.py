# -*- coding:utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"
    _description = "Employee"

    slip_ids = fields.One2many(
        "hr.payslip", "employee_id", string="Payslips", readonly=True
    )
    payslip_count = fields.Integer(
        compute="_compute_payslip_count", groups="sh_hr_payroll.group_hr_payroll_user"
    )
    date_of_joining = fields.Date(string="Date of joining")
    tax_regime = fields.Char(string="Tax Regime")
    pf_account_number = fields.Char(string="PF account number")
    pf_joining_date = fields.Date(string="PF Joining Date")
    pr_account_number = fields.Char(string="PR Account Number (PRAN)")

    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)
