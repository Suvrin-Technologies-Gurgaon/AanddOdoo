from odoo import models, fields, api
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import pytz


class EmpOutOfficeSchedule(models.Model):
    _name = 'emp.out.office.schedule'
    _description = 'Out of Office Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char("Name")
    description = fields.Text("Description")
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True,
                                  default=lambda self: self.env.user.employee_id)
    start_date = fields.Datetime(string="Start Date", required=True)
    end_date = fields.Datetime(string="End Date", required=True)
    state = fields.Selection([('new', 'New'), ('confirmed', 'Confirmed'), ('cancel', 'Cancel')],
                             string="Status", default='new')

    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    def action_cancel_out_of_office_schedule(self):
        """Method to cancel out of office schedule"""
        for rec in self:
            rec.state = 'cancel'

    @api.model
    def auto_create_emp_attendance(self):
        out_employees = self.env['emp.out.office.schedule'].sudo().search([
            ('start_date', '<=', fields.Date.today()),
            ('end_date', '>=', fields.Date.today()),
            ('state', '=', 'confirmed')
        ])
        user_tz = self.env.user.tz or 'UTC'
        tz = pytz.timezone(user_tz)

        for out_employee in out_employees:
            if out_employee.employee_id and out_employee.employee_id.resource_calendar_id and out_employee.employee_id.resource_calendar_id.attendance_ids:
                from_time = out_employee.employee_id.resource_calendar_id.attendance_ids[0].hour_from
                emp_calendar = self.env['resource.calendar.attendance'].sudo().search([
                    ('calendar_id', '=', out_employee.employee_id.resource_calendar_id.id),
                    ('day_period', '=', 'afternoon')
                ], limit=1)
                to_time = emp_calendar.hour_to if emp_calendar else from_time + 8.0  # fallback

                today = fields.Date.today()
                from_date_time = fields.Date.from_string(str(today))

                att_checkin = (datetime.combine(from_date_time, datetime.min.time()) + timedelta(hours=from_time)) - timedelta(hours=5, minutes=30)
                attendance_checkin = (tz.localize(att_checkin).astimezone(pytz.UTC)).replace(tzinfo=None)

                att_checkout = (datetime.combine(from_date_time, datetime.min.time()) + timedelta(hours=to_time)) - timedelta(hours=5, minutes=30)
                attendance_checkout = (tz.localize(att_checkout).astimezone(pytz.UTC)).replace(tzinfo=None)

                existing_attendance = self.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', out_employee.employee_id.id),
                    ('check_in', '>=', datetime.combine(today, datetime.min.time())),
                    ('check_in', '<=', datetime.combine(today, datetime.max.time())),
                ], limit=1)

                if not existing_attendance:
                    vals = {
                        'employee_id': out_employee.employee_id.id,
                        'check_in': attendance_checkin,
                        'check_out': attendance_checkout,
                    }
                    self.env['hr.attendance'].sudo().create(vals)
