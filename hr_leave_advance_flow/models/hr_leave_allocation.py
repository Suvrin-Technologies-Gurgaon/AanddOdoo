from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import UserError


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    @api.model
    def default_get(self, fields_list):
        """Default get to set timeoff type"""
        res = super(HrLeaveAllocation, self).default_get(fields_list)
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
            leave_type = self.env['hr.leave.type'].search([('name', '=', 'Compensatory Days')], limit=1)
            if leave_type:
                res['holiday_status_id'] = leave_type.id
        return res

    @api.model
    def create(self, vals):
        """Set expiry date for Compensatory Days"""
        leave_type = self.env['hr.leave.type'].browse(vals.get('holiday_status_id'))

        if leave_type.name == 'Compensatory Days':
            # Determine start date
            if 'date_from' in vals and vals['date_from']:
                earned_date = fields.Date.to_date(vals['date_from'])
            else:
                earned_date = fields.Date.today()

            month = earned_date.month
            year = earned_date.year

            # Set expiry date based on month
            if 1 <= month <= 9:
                expiry = date(year, 12, 31)
            else:
                expiry = date(year + 1, 3, 31)

            vals['date_from'] = fields.Date.to_string(earned_date)
            vals['date_to'] = fields.Date.to_string(expiry)

        return super(HrLeaveAllocation, self).create(vals)
