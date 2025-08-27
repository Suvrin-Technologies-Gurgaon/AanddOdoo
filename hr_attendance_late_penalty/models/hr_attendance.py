from tabnanny import check

# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, time
import pytz
from markupsafe import Markup
import calendar


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    late_reason = fields.Selection([("late_in", "Late In"), ("early_out", "Early Out")], default=False)
    is_late = fields.Boolean("Is Late ?", default=False)
    is_early_checkout = fields.Boolean("Is Early Checkout?", default=False)
    leave_id = fields.Many2one('hr.leave', string='Late Checkin Time Off')
    early_checkout_leave_id = fields.Many2one('hr.leave', string='Early Checkout Time Off')
    is_send_approval = fields.Boolean("Is send Approval?", default=False)
    is_approved = fields.Boolean("Is Approved?", default=False)
    is_manager = fields.Boolean("Is Manager?", compute="_compute_is_manager", default=False)
    approved_user_id = fields.Many2one('res.users', "Approved User")

    def _compute_is_manager(self):
        for rec in self:
            rec.is_manager = False
            if rec.employee_id and rec.employee_id.attendance_manager_id:
                rec.is_manager = True if rec.employee_id.attendance_manager_id == self.env.user else False

    def write(self, vals):
        res = super(HrAttendance, self).write(vals)
        if 'check_in' in vals and self.is_late and not self.is_approved:
            raise ValidationError("Need Approval From Manager.")
        return res

    def get_pdt_full_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        model_name = self._name
        model_id = self.id
        url = base_url + '/web#id=' + str(model_id) + '&model=' + model_name + '&view_type=form'
        return url

    def action_send_approval_request(self):
        log_user = self.employee_id.attendance_manager_id
        if not log_user:
            raise ValidationError("Add Approval manager in employee profile.")
        if log_user:
            msg = ""
            MailChannel = self.env(context=log_user.context_get())['discuss.channel']
            msg = "<p>Please approve the request to change the checkin time</p>" + \
                  "<p><b>Employee:</b>" + self.employee_id.name + "</p>" + \
                  "<a href =" + self.get_pdt_full_url() + ">" + "Click Here" + "</a>" + ' ' + "to view Record.</p>"

            safe_msg = Markup(msg)
            MailChannel.browse(MailChannel.channel_get([log_user.partner_id.id])['id']).message_post(
                body=_(safe_msg),
                message_type='comment',
                subtype_xmlid='mail.mt_comment')
            self.is_send_approval = True

    def action_checkin_edit_approve(self):
        self.is_approved = True
        self.approved_user_id = self.env.user.id

        # late_or_early = fields.Boolean(string="Late/Early", compute="_compute_late_or_early", store=True)

    # ---------- Core: decide if this attendance is late or early using employee's calendar ----------
    # @api.depends("check_in", "check_out", "employee_id")
    # def _compute_late_or_early(self):
    #     for rec in self:
    #         rec.late_or_early = False
    #         if not rec.check_in or not rec.employee_id:
    #             continue
    #         calendar = rec.employee_id.resource_calendar_id
    #         if not calendar:
    #             continue
    #
    #         # Convert check_in/out to employee's timezone to compare with calendar hours
    #         emp_tz = pytz.timezone(rec.employee_id.tz or self.env.user.tz or "UTC")
    #         check_in_local = fields.Datetime.context_timestamp(rec, rec.check_in).astimezone(emp_tz)
    #         check_out_local = None
    #         if rec.check_out:
    #             check_out_local = fields.Datetime.context_timestamp(rec, rec.check_out).astimezone(emp_tz)
    #
    #         weekday = int(check_in_local.weekday())  # Monday=0
    #         # resource.calendar.attendance uses 0=Monday,...,6=Sunday in 'dayofweek'
    #         day_lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)
    #         if not day_lines:
    #             continue
    #
    #         # work intervals for the day (consider multiple lines like morning/afternoon)
    #         starts = []
    #         ends = []
    #         for a in day_lines:
    #             h_from = time(int(a.hour_from), int(round((a.hour_from % 1) * 60)))
    #             h_to = time(int(a.hour_to), int(round((a.hour_to % 1) * 60)))
    #             starts.append(h_from)
    #             ends.append(h_to)
    #
    #         earliest_start = min(starts) if starts else None
    #         latest_end = max(ends) if ends else None
    #
    #         if earliest_start and check_in_local.time() > earliest_start:
    #             rec.late_or_early = True
    #             rec.late_reason = "late_in"
    #             continue
    #         if latest_end and check_out_local and check_out_local.time() < latest_end:
    #             rec.late_or_early = True
    #             rec.late_reason = "early_out"

    # ---------- Rule: if count exceeds allowed, auto-create half-day leave ----------
    # def _check_permission_count(self):
    #     ICP = self.env["ir.config_parameter"].sudo()
    #     allowed_count = int(ICP.get_param("hr_attendance_late_penalty.late_penalty_days_count", default="2") or 2)
    #     leave_type_id = ICP.get_param("hr_attendance_late_penalty.penalty_leave_type_id")
    #     leave_type_id = int(leave_type_id) if leave_type_id else False
    #     if not leave_type_id:
    #         return  # No leave type configured; skip to avoid errors
    #
    #     for rec in self:
    #         if not rec.late_or_early or not rec.check_in:
    #             continue
    #
    #         # Boundaries of the month in employee tz
    #         emp_tz = pytz.timezone(rec.employee_id.tz or self.env.user.tz or "UTC")
    #         check_in_local = fields.Datetime.context_timestamp(rec, rec.check_in).astimezone(emp_tz)
    #
    #         start_month_local = check_in_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    #         # move to next month then back 1 second
    #         if start_month_local.month == 12:
    #             next_month = start_month_local.replace(year=start_month_local.year + 1, month=1, day=1)
    #         else:
    #             next_month = start_month_local.replace(month=start_month_local.month + 1, day=1)
    #         end_month_local = next_month - timedelta(seconds=1)
    #
    #         # Convert back to UTC for domain search
    #         start_month_utc = pytz.UTC.localize(start_month_local.replace(tzinfo=None)).astimezone(pytz.UTC)
    #         end_month_utc = pytz.UTC.localize(end_month_local.replace(tzinfo=None)).astimezone(pytz.UTC)
    #
    #         count = self.search_count([
    #             ("employee_id", "=", rec.employee_id.id),
    #             ("check_in", ">=", fields.Datetime.to_string(start_month_utc)),
    #             ("check_in", "<=", fields.Datetime.to_string(end_month_utc)),
    #             ("late_or_early", "=", True),
    #         ])
    #
    #         if count > allowed_count:
    #             rec._create_half_day_leave(leave_type_id)

    # def _create_half_day_leave(self, leave_type_id):
    #     # Avoid duplicate penalty leave for the same day
    #     leave_model = self.env["hr.leave"]
    #     existing = leave_model.search([
    #         ("employee_id", "=", self.employee_id.id),
    #         ("holiday_status_id", "=", leave_type_id),
    #         ("request_date_from", "=", fields.Date.to_string(self.check_in.date())),
    #         ("state", "in", ["confirm","validate1","validate","draft"]),
    #         ("name", "=", "Late/Early Penalty"),
    #     ], limit=1)
    #     if existing:
    #         return existing
    #
    #     # Determine half day AM/PM based on reason
    #     period = "am" if self.late_reason == "late_in" else "pm"
    #
    #     vals = {
    #         "name": "Late/Early Penalty",
    #         "employee_id": self.employee_id.id,
    #         "holiday_status_id": leave_type_id,
    #         "request_date_from": self.check_in.date(),
    #         "request_date_to": self.check_in.date(),
    #         "request_unit_half": True,
    #         "request_date_from_period": period,  # am/pm
    #     }
    #     leave = leave_model.create(vals)
    #     return leave

    # ---------- Trigger checks on create/write ----------
    # @api.model
    # def create(self, vals):
    #     rec = super().create(vals)
    #     try:
    #         rec._check_permission_count()
    #     except Exception:
    #         # Do not break attendance creation; log message
    #         self.env.cr.rollback()
    #     return rec
    # #
    # def write(self, vals):
    #     res = super().write(vals)
    #     for rec in self:
    #         try:
    #             rec._check_permission_count()
    #         except Exception:
    #             self.env.cr.rollback()
    #     return res

    def _get_penalty_params(self):
        ICP = self.env["ir.config_parameter"].sudo()
        allowed_count = int(ICP.get_param("hr_attendance_late_penalty.late_penalty_days_count", default="0") or 0)
        leave_type_id = ICP.get_param("hr_attendance_late_penalty.penalty_leave_type_id", False)
        return allowed_count, leave_type_id

    def _get_resource_calendar_attendance(self):
        for rec in self:
            if not rec.check_in or not rec.employee_id:
                False
            calendar = rec.employee_id.resource_calendar_id
            if not calendar:
                False
            weekday = rec.check_in.weekday()
            return calendar.attendance_ids.filtered(
                lambda att: int(att.dayofweek) == weekday
            )

    def _is_early_checkout(self):
        for rec in self:
            resource_calendar = rec._get_employee_calendar()
            if not resource_calendar:
                raise ValidationError(_("Work Schedule is not configured today for this employee."))
            check_in_day = rec.check_in.date()
            half_day_leave = rec.employee_id.leave_ids.filtered(
                lambda l: l.state == 'validate'
                          and l.request_unit_half
                          and l.request_date_from <= rec.check_in.date() <= l.request_date_to
                          and (
                                  (l.request_date_from == check_in_day and l.request_date_from_period in ["am", "pm"])
                                  or (l.request_date_to == check_in_day and l.request_date_to_period in ["am", "pm"])
                          ))
            worked_hrs = sum(
                rec.employee_id.attendance_ids.filtered(lambda x: x.check_in.date() == check_in_day).mapped(
                    'worked_hours'))
            avg_work_hour = resource_calendar.hours_per_day
            if not avg_work_hour or avg_work_hour == 0:
                return False
            if half_day_leave:
                avg_work_hour /= 2
            if worked_hrs < avg_work_hour:
                return True
            return False

    def _check_employee_client_visit(self, employee_id, calendar_resource_attendances):
        """Method to check employee client visit"""
        today = fields.Date.context_today(employee_id)
        user_tz = self.env.user.tz or self.env.company.tz or 'UTC'
        tz = pytz.timezone(user_tz)

        morning_calendar_resource_attendances = calendar_resource_attendances.filtered(
            lambda x: x.day_period == "morning")
        hour_from = morning_calendar_resource_attendances[0].hour_from
        hour_to = morning_calendar_resource_attendances[0].hour_to

        h_from = int(hour_from)
        m_from = int((hour_from - h_from) * 60)
        h_to = int(hour_to)
        m_to = int((hour_to - h_to) * 60)

        work_from = tz.localize(datetime.combine(today, time(hour=h_from, minute=m_from))).astimezone(pytz.UTC)
        work_to = tz.localize(datetime.combine(today, time(hour=h_to, minute=m_to))).astimezone(pytz.UTC)

        client_visit_obj = self.env['hr.client.visit'].search([
            ('employee_id', '=', employee_id.id),
            ('state', '=', 'approved'),
            ('start_time', '<=', work_to),
            ('end_time', '>', work_from)
        ], limit=1)
        return client_visit_obj

    def _is_late_check_in(self):
        for rec in self:
            calendar_resource_attendances = rec._get_resource_calendar_attendance()
            if not calendar_resource_attendances:
                raise ValidationError(_("Work Schedule is not configured today for this employee."))
            check_morning_half_day = rec.employee_id.leave_ids.filtered(
                lambda
                    l: l.state == 'validate' and l.request_unit_half and l.request_date_from <= rec.check_in.date() <= l.request_date_to
                       and ((l.request_date_from == rec.check_in.date() and l.request_date_from_period == "am")
                            or (l.request_date_to == rec.check_in.date())
                            )
            )
            period = 'afternoon' if check_morning_half_day else 'morning'
            actual_check_in_calendar_resource_attendance = calendar_resource_attendances.filtered(
                lambda x: x.day_period == period)
            if not actual_check_in_calendar_resource_attendance:
                actual_check_in_calendar_resource_attendance = min(calendar_resource_attendances.mapped('hour_from'))
            start_hour = actual_check_in_calendar_resource_attendance[0].hour_from
            end_hour = actual_check_in_calendar_resource_attendance[0].hour_to
            emp_tz = pytz.timezone(rec.employee_id.tz or self.env.user.tz or "UTC")
            check_in_local = fields.Datetime.context_timestamp(rec, rec.check_in).astimezone(emp_tz)

            scheduled_start = datetime.combine(
                check_in_local.date(),
                time(hour=int(start_hour), minute=int((start_hour % 1) * 60)),
                tzinfo=check_in_local.tzinfo  # match timezone
            )

            # Check employee client visit
            client_visit = self._check_employee_client_visit(rec.employee_id, calendar_resource_attendances)
            if not client_visit:
                if check_in_local > scheduled_start:
                    return True
                return None
        return None

    def get_last_date_of_current_month(self):
        """method to get last date of current month"""
        today = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        last_day = calendar.monthrange(today.year, today.month)[1]
        first_date_of_current_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_date_of_current_month = today.replace(day=last_day, hour=23, minute=30, second=0, microsecond=0)
        return first_date_of_current_month, last_date_of_current_month

    def _deserve_penalty(self):
        """Method to find deserve penalty"""
        for attendance in self:
            if not attendance.employee_id:
                raise ValidationError(_("Cannot proceed without employee."))
            employee = attendance.employee_id
            allowed_count, leave_type_id = attendance._get_penalty_params()
            if not allowed_count or allowed_count == 0:
                return False
            if not leave_type_id:
                raise ValidationError(
                    _("Oops! It looks like the Penalty Leave Type hasn't been set up yet. Please contact your administrator to get it configured."))
            penalty_leaves = employee.leave_ids.filtered(
                lambda x: x.state in ['validate'] and x.is_penalty_leave).sorted(lambda x: x.request_date_from,
                                                                                 reverse=True)
            recent_penalty_leave = penalty_leaves and penalty_leaves[0] or False
            emp_tz = pytz.timezone(employee.tz or self.env.user.tz or "UTC")

            last_leave_date = fields.Datetime.context_timestamp(employee, employee.create_date).astimezone(emp_tz)

            if recent_penalty_leave:
                last_leave_request_date_to = recent_penalty_leave.request_date_to
                calendar_resource_attendances = attendance._get_resource_calendar_attendance()
                if not calendar_resource_attendances:
                    raise (_("Work Schedule is not configured."))
                # check_in_local = fields.Datetime.context_timestamp(attendance, attendance.check_in).astimezone(emp_tz)

                schedule_hours_to = min(
                    calendar_resource_attendances.filtered(lambda x: x.day_period == "morning").mapped('hour_to'))
                last_leave_date = datetime.combine(
                    last_leave_request_date_to,
                    time(hour=int(schedule_hours_to), minute=int((schedule_hours_to % 1) * 60)),
                    tzinfo=emp_tz  # match timezone
                )

            first_date_of_current_month, last_date_of_current_month = self.get_last_date_of_current_month()
            late_attendances = employee.attendance_ids.filtered(
                lambda x: (x.late_reason and x.check_in and first_date_of_current_month
                           <= fields.Datetime.context_timestamp(x, x.check_in).astimezone(
                            emp_tz) <= last_date_of_current_month))

            # late_attendances = employee.attendance_ids.filtered(lambda x: x.late_reason != False and x.check_in  > last_leave_date)
            if late_attendances and len(late_attendances) > allowed_count:
                return True
            return False
        return None

    def _create_half_day_penalty_leave(self):
        """Method to create half day penalty leave"""
        for attendance in self:
            if attendance._deserve_penalty():
                allowed_count, leave_type_id = attendance._get_penalty_params()
                if not leave_type_id:
                    raise (
                        _("Penalty leave type is not configured in attendance settings,Please contact administrator."))
                check_in_date = attendance.check_in.date()
                # date_from, date_to = attendance.employee_id._check_leave_date(check_in_date, check_in_date)
                vals = {
                    "employee_id": attendance.employee_id and attendance.employee_id.id or False,
                    "holiday_status_id": leave_type_id and int(leave_type_id) or False,
                    "request_date_from": check_in_date,
                    "request_date_to": check_in_date,
                    "request_unit_half": True,
                    "is_penalty_leave": True,
                    "state": "confirm"
                }
                if attendance.is_late and not attendance.is_early_checkout:
                    vals["name"] = "Late Check-in Penalty"
                    vals["request_date_from_period"] = "am"
                    leave = self.env['hr.leave'].sudo().with_context(leave_skip_state_check=True).create(vals)
                    attendance.sudo().write({
                        'leave_id': leave.id
                    })
                elif attendance.is_early_checkout:
                    vals["name"] = "Early Check-out Penalty"
                    vals["request_date_from_period"] = "pm"
                    early_checkout_leave_id = self.env['hr.leave'].sudo().with_context(
                        leave_skip_state_check=True).create(vals)
                    attendance.sudo().write({
                        'early_checkout_leave_id': early_checkout_leave_id.id
                    })
                else:
                    pass
            return None
        return None
