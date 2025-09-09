from tabnanny import check

# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, time
import pytz
from markupsafe import Markup
import calendar
import math
from pytz import timezone, UTC


class HrAttendance(models.Model):
    _name = "hr.attendance"
    _inherit = ["hr.attendance", "mail.thread", "mail.activity.mixin"]

    late_reason = fields.Selection([("late_in", "Late In"), ("early_out", "Early Out")], default=False)
    is_late = fields.Boolean("Is Late ?", default=False)
    is_early_checkout = fields.Boolean("Is Early Checkout?", default=False)
    leave_id = fields.Many2one('hr.leave', string='Late Checkin Time Off')
    early_checkout_leave_id = fields.Many2one('hr.leave', string='Early Checkout Time Off')
    missed_checkout_leave_id = fields.Many2one('hr.leave', string='Missed Checkout Time Off')
    is_send_approval = fields.Boolean("Is send Approval?", default=False)
    is_approved = fields.Boolean("Is Approved?", default=False)
    is_manager = fields.Boolean("Is Manager?", compute="_compute_is_manager", default=False)
    approved_user_id = fields.Many2one('res.users', "Approved User")
    auto_checkout = fields.Boolean(default=False, help="Marked True if auto checkout applied")
    reminder_sent = fields.Boolean(default=False)
    worked_day = fields.Float(string="Worked Days", compute="_compute_days", store=True)
    worked_extra_day = fields.Float(string="Worked Extra Days", compute="_compute_days", store=True)
    extra_day = fields.Float(string="Extra Days", compute="_compute_days", store=True)
    half_day_penalty = fields.Boolean(string="Half Day Penalty Applied", compute="_compute_half_day_penalty", store=True)
    full_day_penalty = fields.Boolean(string="Full Day Penalty Applied", compute="_compute_full_day_penalty", store=True)

    @api.depends('missed_checkout_leave_id')
    def _compute_full_day_penalty(self):
        """Compute stored full-day penalty for filtering, reports, old records."""
        for rec in self:
            if rec.leave_id:
                rec.half_day_penalty = False
            rec.full_day_penalty = bool(rec.missed_checkout_leave_id)

    @api.depends('leave_id', 'early_checkout_leave_id')
    def _compute_half_day_penalty(self):
        """Compute half-day or full-day penalty based on leave and early checkout."""
        for rec in self:
            if rec.leave_id and rec.early_checkout_leave_id:
                rec.full_day_penalty = True
                rec.half_day_penalty = False
            elif rec.leave_id or rec.early_checkout_leave_id:
                rec.full_day_penalty = False
                rec.half_day_penalty = True
            else:
                rec.full_day_penalty = False
                rec.half_day_penalty = False

    @api.depends('worked_hours', 'overtime_hours', 'validated_overtime_hours', 'employee_id')
    def _compute_days(self):
        """Compute days for worked, worked extra and extra with client-friendly rounding"""
        for rec in self:
            hours_per_day = 8.0
            if rec.employee_id and rec.employee_id.resource_calendar_id:
                hours_per_day = rec.employee_id.resource_calendar_id.hours_per_day or hours_per_day

            def round_days(value):
                if not value:
                    return 0.0
                full = math.floor(value)
                fraction = value - full
                if fraction < 0.5:
                    return full
                else:
                    return full + 0.5

            worked_days_raw = rec.worked_hours / hours_per_day if rec.worked_hours else 0.0
            worked_extra_raw = rec.overtime_hours / hours_per_day if rec.overtime_hours else 0.0
            extra_raw = rec.validated_overtime_hours / hours_per_day if rec.validated_overtime_hours else 0.0

            rec.worked_day = round_days(worked_days_raw)
            rec.worked_extra_day = round_days(worked_extra_raw)
            rec.extra_day = round_days(extra_raw)

    def create_full_day_penalty_leave(self, attendance):
        """Method to create full day penalty leave"""
        leave_type_id = attendance.get_timeoff_type_sequentially()
        check_in_date = attendance.check_in.date()

        vals = {
            "name": "Full-day leave penalty applied due to missing checkout.",
            "employee_id": attendance.employee_id and attendance.employee_id.id or False,
            "holiday_status_id": leave_type_id or False,
            "request_date_from": check_in_date,
            "request_date_to": check_in_date,
            "is_penalty_leave": True,
            "state": "confirm"
        }

        if attendance.leave_id:
            vals["name"] = "Missed checkout leave penalty"
            vals["request_date_from_period"] = "pm"
            vals["request_unit_half"] = True

        missed_checkout_leave_id = self.env['hr.leave'].sudo().with_context(leave_skip_state_check=True).create(vals)
        attendance.sudo().write({
            'missed_checkout_leave_id': missed_checkout_leave_id.id
        })

    @api.model
    def _cron_check_attendance(self):
        """Cron to remind + auto-checkout employees with timezone-safe handling."""
        now_utc = fields.Datetime.now()  # naive UTC
        now_utc_naive = now_utc.replace(tzinfo=None)

        # Get all open attendances
        open_attendances = self.search([('check_out', '=', False)])
        res_model_id = self.env['ir.model']._get('hr.attendance').id
        activity_type = self.env.ref('mail.mail_activity_data_todo')

        for attendance in open_attendances:
            employee = attendance.employee_id
            if not employee or not employee.user_id:
                continue

            # Use employee's timezone, fallback to UTC
            user_tz = timezone(employee.user_id.tz or 'UTC')

            # Convert check_in to local timezone
            check_in_local = attendance.check_in.replace(tzinfo=UTC).astimezone(user_tz)
            # today_local = now_utc.replace(tzinfo=UTC).astimezone(user_tz).date()

            # --- Case A: Old attendance (previous days, no checkout)
            # if check_in_local.date() < today_local:
            #     old_midnight_local = datetime.combine(
            #         check_in_local.date(),
            #         datetime.max.time()
            #     ).replace(hour=23, minute=59, second=59, microsecond=0)
            #
            #     old_midnight_utc = user_tz.localize(old_midnight_local).astimezone(UTC).replace(tzinfo=None)
            #
            #     attendance.write({
            #         'check_out': old_midnight_utc,
            #         'auto_checkout': True,
            #     })
            #     continue

                # --- Case B: Today's attendance
            calendar = employee.resource_calendar_id
            if not calendar:
                continue

            weekday = str(now_utc.replace(tzinfo=UTC).astimezone(user_tz).weekday())
            shifts_today = calendar.attendance_ids.filtered(lambda s: s.dayofweek == weekday)
            if not shifts_today:
                continue

            # Last shift = afternoon shift
            afternoon_shift = max(shifts_today, key=lambda s: s.hour_to)

            # Shift end in local tz
            shift_end_local = check_in_local.replace(
                hour=int(afternoon_shift.hour_to),
                minute=int(round((afternoon_shift.hour_to % 1) * 60)),
                second=0,
                microsecond=0
            )

            # Shift end UTC naive for comparison
            shift_end_utc_naive = shift_end_local.astimezone(UTC).replace(tzinfo=None)

            # --- Reminder: 5 minutes after shift end
            reminder_time_utc = shift_end_utc_naive + timedelta(minutes=5)

            if shift_end_utc_naive < now_utc_naive >= reminder_time_utc and not attendance.reminder_sent:
                self.env['mail.activity'].create({
                    'res_model_id': res_model_id,
                    'res_id': attendance.id,
                    'activity_type_id': activity_type.id,
                    'summary': "Checkout Reminder",
                    'user_id': employee.user_id.id,
                    'note': "Please check out",
                    'date_deadline': fields.Date.today(),
                })

                attendance.message_post(
                    body=f"Your checkout is scheduled at {shift_end_local.strftime('%H:%M')} (local time).",
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    partner_ids=[employee.user_id.partner_id.id],
                )

                # Send inbox notification
                self.env['mail.notification'].sudo().create({
                    'res_partner_id': employee.user_id.partner_id.id,
                    'mail_message_id': self.env['mail.message'].create({
                        'body': f"Dear {employee.name}, please don't forget to checkout.",
                        'subject': "Checkout Reminder",
                        'message_type': 'notification',
                        'model': 'hr.attendance',
                        'res_id': attendance.id,
                    }).id,
                    'notification_type': 'inbox',
                    'is_read': False,
                })

                attendance.reminder_sent = True

            # --- Auto checkout at midnight today (local)
            yesterday_local = (now_utc.replace(tzinfo=UTC).astimezone(user_tz) - timedelta(days=1))
            midnight_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=0)

            # Convert to UTC naive for DB storage
            midnight_utc_naive = midnight_local.astimezone(UTC).replace(tzinfo=None)

            if now_utc_naive >= midnight_utc_naive and not attendance.auto_checkout:
                attendance.write({
                    'check_out': midnight_utc_naive,
                    'auto_checkout': True,
                })
                # Create Full day Penalty Leave
                self.create_full_day_penalty_leave(attendance)

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
            calendar_resource_attendances = rec._get_resource_calendar_attendance()
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
            # Check employee client visit
            client_visit = self._check_employee_client_visit(rec.employee_id, calendar_resource_attendances)
            # Check employee client visit shift
            morning_shift = self._check_client_visit_in_morning_shift(rec.employee_id, calendar_resource_attendances)
            if morning_shift:
                avg_work_hour /= 2
            if not client_visit:
                if worked_hrs < avg_work_hour:
                    return True
            return False
        return None

    def _check_employee_client_visit(self, employee_id, calendar_resource_attendances):
        """Method to check employee client visit"""
        today = fields.Date.context_today(employee_id)
        user_tz = self.env.user.tz or self.env.company.tz or 'UTC'
        tz = pytz.timezone(user_tz)

        if self.check_in and not self.check_out:
            shift_period = "morning"
        elif self.check_in and self.check_out:
            shift_period = "afternoon"
        else:
            return False

        morning_calendar_resource_attendances = calendar_resource_attendances.filtered(
            lambda x: x.day_period == shift_period)
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

    def _check_client_visit_in_morning_shift(self, employee_id, calendar_resource_attendances):
        """Return client visit for a specific shift (morning or afternoon)."""
        today = fields.Date.context_today(employee_id)
        user_tz = self.env.user.tz or self.env.company.tz or 'UTC'
        tz = pytz.timezone(user_tz)

        selected_attendance = calendar_resource_attendances.filtered(
            lambda x: x.day_period == "morning"
        )
        if not selected_attendance:
            return None

        hour_from = selected_attendance[0].hour_from
        hour_to = selected_attendance[0].hour_to

        h_from, m_from = divmod(int(hour_from * 60), 60)
        h_to, m_to = divmod(int(hour_to * 60), 60)

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

    def get_timeoff_type_sequentially(self):
        """Method to get timeoff type sequentially"""
        employee = self.employee_id
        if employee:
            unpaid_leave_type = self.env['hr.leave.type'].search([('name', '=', 'Unpaid')], limit=1)
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
                    return leave_type.id

            if not leave_found and unpaid_leave_type:
                return unpaid_leave_type.id
            return None
        return None

    def _create_half_day_penalty_leave(self):
        """Method to create half day penalty leave"""
        for attendance in self:
            if attendance._deserve_penalty():
                allowed_count, leave_type_id = attendance._get_penalty_params()
                # if not leave_type_id:
                #     raise (
                #         _("Penalty leave type is not configured in attendance settings,Please contact administrator."))
                leave_type_id = attendance.get_timeoff_type_sequentially()

                check_in_date = attendance.check_in.date()
                # date_from, date_to = attendance.employee_id._check_leave_date(check_in_date, check_in_date)
                vals = {
                    "employee_id": attendance.employee_id and attendance.employee_id.id or False,
                    "holiday_status_id": leave_type_id or False,
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
