# -*- coding: utf-8 -*-
from odoo import fields, models


class HrLoanLine(models.Model):
    """ Model for managing details of loan request installments"""
    _name = "hr.loan.line"
    _description = "Installment Line"

    date = fields.Date(string="Payment Date", required=True,
                       help="Date of the payment")
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  help="Employee")
    amount = fields.Float(string="Amount", required=True, help="Amount")
    paid = fields.Boolean(string="Paid", help="Indicates whether the "
                                              "installment has been paid.")
    loan_id = fields.Many2one('hr.loan', string="Loan Ref.",
                              help="Reference to the associated loan.")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip Ref.",
                                 help="Reference to the associated "
                                      "payslip, if any.")
