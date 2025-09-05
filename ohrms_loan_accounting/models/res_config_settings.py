# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccConfig(models.TransientModel):
    """ Added boolean fields which can approve loan by enabling True"""
    _inherit = 'res.config.settings'

    loan_approve = fields.Boolean(default=False,
                                  string="Approval from Accounting Department",
                                  help="Loan Approval from account manager")

    @api.model
    def get_values(self):
        """ Get the values to the config parameter"""
        res = super(AccConfig, self).get_values()
        res.update(
            loan_approve=self.env['ir.config_parameter'].sudo().get_param(
                'account.loan_approve'))
        return res

    def set_values(self):
        """ Set values to the config parameter"""
        super(AccConfig, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'account.loan_approve', self.loan_approve)
