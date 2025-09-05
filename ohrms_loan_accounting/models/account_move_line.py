# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveLine(models.Model):
    """ Added loan id information on invoice line"""
    _inherit = "account.move.line"

    loan_id = fields.Many2one('hr.loan', string='Loan Id',
                              help="Loan id on invoice line")
