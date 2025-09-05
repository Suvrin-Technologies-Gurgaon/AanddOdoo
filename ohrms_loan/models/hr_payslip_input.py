# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipInput(models.Model):
    """  Extends the 'hr.payslip.input' model to include additional
    fields related to loan information and date details"""
    _inherit = 'hr.payslip.input'

    loan_line_id = fields.Many2one('hr.loan.line',
                                   string="Loan Installment",
                                   help="Loan installment associated "
                                        "with this payslip input.")
    date_to = fields.Date(string="Date To", help="End date for the "
                                                 "payslip input.")
    date_from = fields.Date(string='Date from', help="Start date for the "
                                                     "payslip input.")
