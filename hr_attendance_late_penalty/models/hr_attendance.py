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
    is_local_tour = fields.Boolean(default=False)
    worked_day = fields.Float(string="Worked Days", compute="_compute_work_day", store=True)
    worked_extra_day = fields.Float(string="Worked Extra Days", compute="_compute_work_day", store=True)
    extra_day = fields.Float(string="Extra Days", compute="_compute_work_day", store=True)
    half_day_penalty = fields.Boolean(string="Half Day Penalty Applied", compute="_compute_half_day_penalty", store=True)
    full_day_penalty = fields.Boolean(string="Full Day Penalty Applied", compute="_compute_full_day_penalty", store=True)

    #######################
     # Compute Methods
    #######################

    @api.depends('check_in', 'check_out', 'auto_checkout', 'employee_id')
    def _compute_worked_hours(self):
        """Override to ensure auto-checkout uses evening shift end instead of midnight."""
        for rec in self:
            worked = 0.0
            overtime = 0.0

            if rec.check_in and rec.check_out and rec.employee_id:
                effective_checkout = rec.check_out

                if rec.auto_checkout:
                    user_tz = timezone(rec.employee_id.tz or self.env.user.tz or "UTC")
                    check_in_local = rec.check_in.replace(tzinfo=UTC).astimezone(user_tz)
                    calendar = rec.employee_id.resource_calendar_id

                    if calendar:
                        weekday = str(check_in_local.weekday())
                        shifts_today = calendar.attendance_ids.filtered(lambda s: s.dayofweek == weekday)

                        if shifts_today:
                            # Get the latest shift (end of the day)
                            evening_shift = max(shifts_today, key=lambda s: s.hour_to)
                            h_to = int(evening_shift.hour_to)
                            m_to = int((evening_shift.hour_to - h_to) * 60)

                            shift_end_local = datetime.combine(
                                check_in_local.date(), time(hour=h_to, minute=m_to)
                            )
                            shift_end_local = user_tz.localize(shift_end_local)
                            shift_end_utc = shift_end_local.astimezone(UTC).replace(tzinfo=None)

                            # Cap worked hours at shift end
                            effective_checkout = min(rec.check_out, shift_end_utc)

                            # Compute overtime if actual checkout is later than shift end
                            if rec.check_out > shift_end_utc:
                                overtime = (rec.check_out - shift_end_utc).total_seconds() / 3600.0

                # Compute worked hours (capped if auto checkout)
                worked = (effective_checkout - rec.check_in).total_seconds() / 3600.0

            rec.worked_hours = worked
            rec.validated_overtime_hours = overtime

    @api.depends('missed_checkout_leave_id')
    def _compute_full_day_penalty(self):
        """Compute stored full-day penalty for filtering, reports, old records."""
        for rec in self:
            morning_leave = bool(rec.check_morning_half_day_leave(rec))
            evening_leave = bool(rec.check_evening_half_day_leave(rec))
            has_half_day_leave = morning_leave or evening_leave

            # Full-day penalty only if missed checkout exists
            if rec.missed_checkout_leave_id:
                if has_half_day_leave:
                    rec.half_day_penalty = True
                elif (
                        not rec.leave_id
                        or not rec.early_checkout_leave_id
                ):
                    rec.full_day_penalty = True

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

    @api.depends("check_in", "check_out", "employee_id", "auto_checkout", "leave_id", "early_checkout_leave_id")
    def _compute_work_day(self):
        """Compute method to get work day"""
        for rec in self:
            # default
            rec.worked_day = 0.0

            # need both check-in and check-out
            if not rec.check_in or not rec.check_out:
                continue

            # auto checkout → 0 worked days
            if rec.auto_checkout:
                rec.worked_day = 0.0
                continue

            # flags
            morning_leave = bool(rec.check_morning_half_day_leave(rec))
            evening_leave = bool(rec.check_evening_half_day_leave(rec))
            has_late_penalty = bool(rec.leave_id)  # late check-in
            has_early_penalty = bool(rec.early_checkout_leave_id)  # early checkout
            deserve_penalty = rec._deserve_penalty()

            # --- Perfect attendance (no penalties, no half-day leaves) ---
            if not (has_late_penalty or has_early_penalty or morning_leave or evening_leave):
                rec.worked_day = 1.0
                continue

            # --- If penalty does NOT apply, follow forgiving rules ---
            if not deserve_penalty:
                # penalties forgiven => full day
                if has_late_penalty or has_early_penalty:
                    rec.worked_day = 1.0
                    continue
                # two half-day leaves => full day
                if morning_leave and evening_leave:
                    rec.worked_day = 1.0
                    continue
                # single half-day leave => 0.5
                if morning_leave or evening_leave:
                    rec.worked_day = 0.5
                    continue
                # fallback
                rec.worked_day = 1.0
                continue

            # --- Penalty applies: evaluate specific combinations first ---

            # both penalties => 0
            if has_late_penalty and has_early_penalty:
                rec.worked_day = 0.0
                continue

            # both half-day leaves present
            if morning_leave and evening_leave:
                # if any penalty present → 0, else full day
                if has_late_penalty or has_early_penalty:
                    rec.worked_day = 0.0
                else:
                    rec.worked_day = 1.0
                continue

            # morning half-day rules: (check special combos before generic penalty-only)
            if morning_leave:
                # if any penalty present with morning half-day → 0 (user requirement)
                if has_late_penalty or has_early_penalty:
                    rec.worked_day = 0.0
                else:
                    rec.worked_day = 0.5
                continue

            # evening half-day rules
            if evening_leave:
                if has_late_penalty or has_early_penalty:
                    rec.worked_day = 0.0
                else:
                    rec.worked_day = 0.5
                continue

            # only late penalty (no half-day leaves)
            if has_late_penalty:
                rec.worked_day = 0.5
                continue

            # only early penalty (no half-day leaves)
            if has_early_penalty:
                rec.worked_day = 0.5
                continue

            # default fallback
            rec.worked_day = 0.0

    def create_full_day_penalty_leave(self, attendance):
        """Method to create full day penalty leave"""
        HrLeave = self.env['hr.leave'].sudo().with_context(leave_skip_state_check=True)

        check_in_date = attendance.check_in.date()

        has_morning_half_day = self.check_morning_half_day_leave(attendance)
        has_evening_half_day = self.check_evening_half_day_leave(attendance)
        requested_days = 1.0

        # Default: full-day penalty
        vals = {
            "name": "Full-day leave penalty applied due to missing checkout",
            "employee_id": attendance.employee_id.id,
            "request_date_from": check_in_date,
            "request_date_to": check_in_date,
            "is_penalty_leave": True,
            "state": "confirm",
            "request_unit_half": False,
            "request_date_from_period": False
        }

        # Case 1: Already has leave → skip
        if (has_morning_half_day and attendance.leave_id) or (has_evening_half_day and attendance.leave_id):
            return False

        # Case 2: Morning half-day available → create afternoon penalty
        if has_morning_half_day and not attendance.leave_id:
            vals.update({
                "name": "Missed checkout leave penalty",
                "request_date_from_period": "pm",
                "request_unit_half": True,
            })
            requested_days = 0.5

        # Case 3: Evening half-day available → create morning penalty
        elif has_evening_half_day and not attendance.leave_id:
            vals.update({
                "name": "Missed checkout leave penalty",
                "request_date_from_period": "am",
                "request_unit_half": True,
            })
            requested_days = 0.5

        # Case 4: Fallback (already has leave but still needs penalty)
        elif attendance.leave_id:
            vals.update({
                "name": "Missed checkout leave penalty",
                "request_date_from_period": "pm",
                "request_unit_half": True,
            })
            requested_days = 0.5

        leave_type_id = attendance.get_timeoff_type_sequentially(requested_days)
        if not leave_type_id:
            return False

        vals.update({
            "holiday_status_id": leave_type_id,
        })

        # Create leave
        leave = HrLeave.create(vals)
        attendance.sudo().write({"missed_checkout_leave_id": leave.id})
        return leave

    def check_morning_half_day_leave(self, attendance):
        """Method to check morning half day leave"""
        check_in_date = attendance.check_in.date()
        return attendance.employee_id.leave_ids.filtered(
            lambda l: l.state == 'validate' and l.request_unit_half and l.request_date_from == check_in_date
                      and l.request_date_from_period == "am")

    def check_evening_half_day_leave(self, attendance):
        """Method to check evening half day leave"""
        check_in_date = attendance.check_in.date()
        return attendance.employee_id.leave_ids.filtered(
            lambda l: l.state == 'validate' and l.request_unit_half and l.request_date_from == check_in_date
                      and l.request_date_from_period == "pm")

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
                checkout_local = user_tz.localize(datetime.combine(check_in_local.date(), time(23, 59, 59)))
                checkout_utc_naive = checkout_local.astimezone(UTC).replace(tzinfo=None)

                if now_utc_naive >= checkout_utc_naive and not attendance.auto_checkout:
                    attendance.write({
                        'check_out': checkout_utc_naive,
                        'auto_checkout': True,
                    })
                self.create_full_day_penalty_leave(attendance)
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
            # yesterday_local = (now_utc.replace(tzinfo=UTC).astimezone(user_tz) - timedelta(days=1))
            # midnight_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=0)

            # Convert to UTC naive for DB storage
            # midnight_utc_naive = midnight_local.astimezone(UTC).replace(tzinfo=None)

            checkout_local = user_tz.localize(datetime.combine(check_in_local.date(), time(23, 59, 59)))

            # Convert back to UTC naive for DB
            checkout_utc_naive = checkout_local.astimezone(UTC).replace(tzinfo=None)

            if now_utc_naive >= checkout_utc_naive and not attendance.auto_checkout:
                attendance.write({
                    'check_out': checkout_utc_naive,
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
            client_visit, days_count = self._check_employee_client_visit(rec.employee_id)
            # Check employee client visit shift
            # morning_shift = self._check_client_visit_in_morning_shift(rec.employee_id, calendar_resource_attendances)
            # if morning_shift:
            #     avg_work_hour /= 2
            if client_visit:
                if days_count == 1:
                    rec.is_local_tour = True
                    return False
                elif days_count > 1:
                    rec._evaluate_visit_and_open_next_day_window(client_visit)
                    return False

            # If no client_visit OR after handling client_visit logic
            if worked_hrs < avg_work_hour:
                return True
            return False
        return None

    def _check_employee_client_visit(self, employee_id):
        """Method to check employee client visit"""
        today = fields.Date.context_today(employee_id)
        user_tz = self.env.user.tz or self.env.company.tz or 'UTC'
        tz = pytz.timezone(user_tz)

        # Convert today's start and end to UTC
        date_start = tz.localize(datetime.combine(today, time.min)).astimezone(pytz.UTC)
        date_end = tz.localize(datetime.combine(today, time.max)).astimezone(pytz.UTC)

        # Find client visit where today falls between start_time and end_time
        client_visit_obj = self.env['hr.client.visit'].search([
            ('employee_id', '=', employee_id.id),
            ('state', '=', 'approved'),
            ('start_time', '<=', date_end),
            ('end_time', '>=', date_start),
        ], limit=1)

        if not client_visit_obj:
            return False, 0

        # Convert to local timezone for day calculation
        start_local = client_visit_obj.start_time.astimezone(tz).date()
        end_local = client_visit_obj.end_time.astimezone(tz).date()

        days_count = (end_local - start_local).days + 1

        return client_visit_obj, days_count

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

    def _consume_late_checkin_window_if_applicable(self):
        """When employee checks in, consume the late window if within allowed time."""
        for rec in self:
            emp = rec.employee_id
            if not emp.tomorrow_late_checkin_window_open or not rec.check_in:
                return False
            allowed_until = emp.tomorrow_late_checkin_window_until
            if not allowed_until:
                emp.write({
                    "tomorrow_late_checkin_window_open": False,
                    "tomorrow_late_checkin_window_until": False,
                })
                return False
            if rec.check_in <= allowed_until:
                # Allowed → consume
                emp.write({
                    "tomorrow_late_checkin_window_open": False,
                    "tomorrow_late_checkin_window_until": False,
                })
                return True
            else:
                # Expired → clear flag
                emp.write({
                    "tomorrow_late_checkin_window_open": False,
                    "tomorrow_late_checkin_window_until": False,
                })
                return None
        return None

    def _evaluate_visit_and_open_next_day_window(self, client_visit):
        """Method to evaluate visit and open next day window"""
        for rec in self:
            emp = rec.employee_id
            if not emp or not rec.check_out:
                continue

            visit = client_visit
            if not visit:
                continue

            tz_str = emp.user_id.tz or self.env.user.tz or "UTC"
            try:
                user_tz = pytz.timezone(tz_str)
            except Exception:
                user_tz = pytz.UTC

            start_local = visit.start_time.replace(tzinfo=pytz.UTC).astimezone(user_tz)
            end_local = visit.end_time.replace(tzinfo=pytz.UTC).astimezone(user_tz)
            checkout_local = rec.check_out.replace(tzinfo=pytz.UTC).astimezone(user_tz)

            spans_multi = end_local.date() > start_local.date()
            same_date = checkout_local.date() == end_local.date()
            checkout_after_23 = checkout_local.time() >= time(23, 0, 0)

            if spans_multi and same_date and checkout_after_23:
                allowed_local_dt = datetime.combine(
                    end_local.date() + timedelta(days=1), time(11, 0, 0)
                )
                allowed_local = user_tz.localize(allowed_local_dt)
                allowed_utc = allowed_local.astimezone(pytz.UTC).replace(tzinfo=None)
                emp.write({
                    "tomorrow_late_checkin_window_open": True,
                    "tomorrow_late_checkin_window_until": allowed_utc,
                })

    def _is_late_check_in(self):
        for rec in self:
            calendar_resource_attendances = rec._get_resource_calendar_attendance()
            if not calendar_resource_attendances:
                raise ValidationError(_("Work Schedule is not configured today for this employee."))

            check_in_date = rec.check_in.date()
            check_morning_half_day = rec.employee_id.leave_ids.filtered(
            lambda l: l.state == 'validate' and l.request_unit_half and l.request_date_from == check_in_date
                      and l.request_date_from_period == "am")

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
            client_visit, days_count = self._check_employee_client_visit(rec.employee_id)
            if client_visit:
                rec.is_local_tour = True
                return None
            else:
                consume = rec._consume_late_checkin_window_if_applicable()
                if consume:
                    return None

                # --- Late logic ---
            if period == "afternoon":
                # If half-day morning leave, apply 1 mins grace
                grace_time = scheduled_start + timedelta(minutes=1)
                return check_in_local > grace_time
            else:
                # Otherwise use old logic (any check-in after shift start = late)
                return check_in_local > scheduled_start
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
            # if not leave_type_id:
            #     raise ValidationError(
            #         _("Oops! It looks like the Penalty Leave Type hasn't been set up yet. Please contact your administrator to get it configured."))
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

    def get_timeoff_type_sequentially(self, requested_days):
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
                    if self.auto_checkout and requested_days > 0.5:
                        if available_days >= 1.0:
                            return leave_type.id
                    else:
                        return leave_type.id

            if not leave_found and unpaid_leave_type:
                return unpaid_leave_type.id
            return None
        return None

    def _create_half_day_penalty_leave(self):
        """Method to create half day penalty leave"""
        HrLeave = self.env['hr.leave'].sudo().with_context(leave_skip_state_check=True)
        for attendance in self:
            if attendance._deserve_penalty():
                allowed_count, leave_type_id = attendance._get_penalty_params()
                # if not leave_type_id:
                #     raise (
                #         _("Penalty leave type is not configured in attendance settings,Please contact administrator."))
                leave_type_id = attendance.get_timeoff_type_sequentially(requested_days=0.5)

                check_in_date = attendance.check_in.date()

                # Determine half-day availability
                has_morning_half_day = self.check_morning_half_day_leave(attendance)
                has_evening_half_day = self.check_evening_half_day_leave(attendance)

                vals = {
                    "employee_id": attendance.employee_id.id,
                    "holiday_status_id": leave_type_id,
                    "request_date_from": check_in_date,
                    "request_date_to": check_in_date,
                    "request_unit_half": True,
                    "is_penalty_leave": True,
                    "state": "confirm",
                }

                # Case 1: Late check-in
                if attendance.is_late and not attendance.is_early_checkout:
                    vals["name"] = "Late Check-in Penalty"
                    vals["request_date_from_period"] = "pm" if has_morning_half_day else "am"

                    leave = HrLeave.create(vals)
                    attendance.sudo().write({"leave_id": leave.id})
                    continue

                # Case 2: Early check-out
                if attendance.is_early_checkout:
                    # Prevent duplicate leave creation
                    if (has_morning_half_day and attendance.leave_id) or (has_evening_half_day and attendance.leave_id):
                        continue

                    vals.update({
                        "name": "Early Check-out Penalty",
                    })

                    if has_morning_half_day and not attendance.leave_id:
                        vals["request_date_from_period"] = "pm"
                    elif has_evening_half_day and not attendance.leave_id:
                        vals["request_date_from_period"] = "am"
                    else:
                        vals["request_date_from_period"] = "pm"

                    early_leave = HrLeave.create(vals)
                    attendance.sudo().write({"early_checkout_leave_id": early_leave.id})
                    continue
            return None
        return None
