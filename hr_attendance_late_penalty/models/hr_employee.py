from odoo import models, fields, api, _
from datetime import datetime, timedelta, time
from odoo.exceptions import AccessError, MissingError, ValidationError, UserError
from dateutil.relativedelta import relativedelta

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    leave_ids = fields.One2many('hr.leave', 'employee_id', string='Leaves')
    tomorrow_late_checkin_window_open = fields.Boolean(
        string="Tomorrow Late Check-in Window Open",
        help="If True, employee can check-in late until tomorrow_late_checkin_window_until.",
        default=False,
    )
    tomorrow_late_checkin_window_until = fields.Datetime(
        string="Late Check-in Allowed Until (UTC)",
        help="UTC datetime until which next-day late check-in is allowed.",
    )

    def _clear_expired_late_windows(self):
        """Clear expired windows daily (via cron)."""
        now = fields.Datetime.now()
        expired = self.search([
            ("tomorrow_late_checkin_window_open", "=", True),
            ("tomorrow_late_checkin_window_until", "<", now),
        ])
        if expired:
            expired.write({
                "tomorrow_late_checkin_window_open": False,
                "tomorrow_late_checkin_window_until": False,
            })

    def _attendance_action_change(self, geo_information=None):
        attendance = super()._attendance_action_change(geo_information=geo_information)
        if attendance:
            if not self.resource_calendar_id:
                raise (_("Your work schedule is not configured yet. Please contact admin."))
            if attendance.check_in and not attendance.check_out:
                first_attendance = self._get_first_or_last_attendance_of_the_day(attendance.check_in)
                if first_attendance != attendance:
                    if first_attendance.employee_id and first_attendance.check_in and first_attendance.check_out:
                        raise ValidationError(_("%s - Already attendance marked for today", first_attendance.employee_id.name))

                # Check Work from home
                if not self._is_work_from_home(attendance.employee_id):
                    if first_attendance and first_attendance._is_late_check_in():
                        if first_attendance.late_reason != 'late_in':
                            first_attendance.sudo().write({
                                'late_reason': 'late_in',
                                'is_late': True
                            })
                        first_attendance._create_half_day_penalty_leave()

            elif attendance.check_in and attendance.check_out:
                self._check_early_checkout(attendance)
        return attendance

    def _check_early_checkout(self, attendance):
        """Method to check early check out"""
        last_attendance = self._get_first_or_last_attendance_of_the_day(attendance.check_out)
        if last_attendance != attendance:
            return attendance

        # Check Work from home
        if not self._is_work_from_home(attendance.employee_id):
            if last_attendance and last_attendance._is_early_checkout():
                if last_attendance.late_reason != 'early_out':
                    last_attendance.sudo().write({
                        'late_reason': 'early_out',
                        'is_early_checkout': True
                    })
                last_attendance._create_half_day_penalty_leave()
                return None

        return None

    def _get_first_or_last_attendance_of_the_day(self, date_to_check, last=False):
        if not date_to_check:
            return False
        check_in = date_to_check.date()
        check_in_day_start = datetime.combine(check_in, time.min)
        check_in_day_end = datetime.combine(check_in, time.max)
        attendances = self.attendance_ids.filtered(
            lambda att: att.check_in and check_in_day_start <= att.check_in <= check_in_day_end
        )
        if attendances:
            ind = -1 if last else 0
            return attendances.sorted(key=lambda att: att.check_in)[ind]
        return False

    def _leave_today(self):
        date_to_check = datetime.now()
        for x in self.leave_ids:
            if x.state == 'validate' and x.request_date_from <= date_to_check.date() <= x.request_date_to and not x.request_unit_half:

                return True
        return self.leave_ids.filtered(lambda x: x.request_date_from <= date_to_check.date() <= x.request_date_to
                          and x.state == 'validate' and not x.request_unit_half)
    # @api.model
    # def _action_trigger_early_checkout_penalty(self):
    #     employees = self.search([('resource_calendar_id', '!=', False), ('contract_id', '!=', False)])
    #     for employee in employees.filtered(lambda x: x.id == 332):
    #         if employee._leave_today():
    #             continue
    #         date_to_check = datetime.now()
    #         last_attendance = employee._get_first_or_last_attendance_of_the_day(date_to_check, last=True)
    #         if not last_attendance:
    #             continue
    #         if last_attendance._is_early_checkout():
    #             last_attendance.sudo().write({
    #                 'late_reason': 'early_out'
    #             })
    #             last_attendance._create_half_day_penalty_leave()

    def _check_leave_date(self, date_from, date_to):
        for employee in self:
            valid_day = True
            overlapping_leaves = self.search([
                ('date_from', '<', date_to),
                ('date_to', '>', date_from),
                ('employee_id', '=', employee.id),
                ('state', 'not in', ['cancel', 'refuse']),
            ])
            if overlapping_leaves:
                valid_day = False
            calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
            if calendar:
                overlapping_holidays = self.env['resource.calendar.leaves'].search([
                    ('calendar_id', '=', calendar.id),
                    ('date_from', '<', date_to),
                    ('date_to', '>', date_from),
                ])
                if overlapping_holidays:
                    valid_day = False
            if not valid_day:
                date_from += relativedelta(days=1)
                date_to += relativedelta(days=1)
                employee._check_leave_date(date_from, date_to)
            return date_from, date_to

