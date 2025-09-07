from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def carry_forward_sick_leave(self):
        """Method to carry forward sick leave"""
        sick_leave_type = self.env['hr.leave.type'].search([('name', '=', 'Sick Leave')], limit=1)
        if not sick_leave_type:
            return

        next_year = date.today().year + 1
        employees = self.sudo().search([('active', '=', True)])

        for employee in employees:
            existing = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', sick_leave_type.id),
                ('date_from', '>=', f'{next_year}-01-01'),
                ('date_to', '<=', f'{next_year}-12-31')
            ])
            if existing:
                continue

            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', sick_leave_type.id),
                ('state', '=', 'validate'),
                ('date_from', '>=', f'{date.today().year}-01-01'),
                ('date_to', '<=', f'{date.today().year}-12-31')
            ])
            total_allocated = sum(a.number_of_days for a in allocations)

            leaves_taken = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', sick_leave_type.id),
                ('state', '=', 'validate'),
                ('request_date_from', '>=', f'{date.today().year}-01-01'),
                ('request_date_to', '<=', f'{date.today().year}-12-31')
            ])
            total_taken = sum(l.number_of_days for l in leaves_taken)

            unused_days = total_allocated - total_taken
            if unused_days > 30:
                unused_days = 30

            if unused_days > 0:
                self.env['hr.leave.allocation'].create({
                    'name': f'Earned Leave {next_year}',
                    'employee_id': employee.id,
                    'holiday_status_id': sick_leave_type.id,
                    'number_of_days': unused_days,
                    'allocation_type': 'regular',
                    'date_from': f'{next_year}-01-01',
                    'date_to': f'{next_year}-12-31'
                })


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    calendar_event_id = fields.Many2one('calendar.event', string="Calendar Event")

    @api.model
    def default_get(self, fields_list):
        """Override default get to set timeoff type"""
        res = super(HrLeave, self).default_get(fields_list)
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        unpaid_leave_type = self.env['hr.leave.type'].search([('name', '=', 'Unpaid')], limit=1)
        if employee:
            # Get leave types ordered by sequence
            leave_types = self.env['hr.leave.type'].search([], order='sequence asc')
            leave_found = False

            for leave_type in leave_types:
                # Check if employee has remaining allocation
                remaining_alloc = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', employee.id),
                    ('holiday_status_id', '=', leave_type.id),
                    ('state', '=', 'validate')
                ])
                total_allocated = sum(a.number_of_days for a in remaining_alloc)
                leaves_taken = self.env['hr.leave'].search([
                    ('employee_id', '=', employee.id),
                    ('holiday_status_id', '=', leave_type.id),
                    ('state', 'not in', ['refuse', 'cancel'])
                ])
                total_taken = sum(l.number_of_days for l in leaves_taken)
                available_days = total_allocated - total_taken
                if available_days > 0:
                    res['holiday_status_id'] = leave_type.id
                    leave_found = True
                    break

            if not leave_found and unpaid_leave_type:
                res['holiday_status_id'] = unpaid_leave_type.id
        return res
