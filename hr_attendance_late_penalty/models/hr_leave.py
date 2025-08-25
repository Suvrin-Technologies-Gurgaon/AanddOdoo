from odoo import models, fields, api, _


class HRLeave(models.Model):
    _inherit = 'hr.leave'

    def _compute_cancel_permission(self):
        for rec in self:
            show_cancel_button = True
            if rec.is_penalty_leave and not self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                show_cancel_button = False
            rec.show_cancel_button = show_cancel_button

    is_penalty_leave = fields.Boolean(string='Is Penalty Leave', default=False)
    show_cancel_button = fields.Boolean(string="Show Cancel Option", compute='_compute_cancel_permission')
