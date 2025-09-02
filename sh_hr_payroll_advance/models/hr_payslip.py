from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import UserError
from datetime import timedelta
from datetime import datetime
from dateutil.relativedelta import relativedelta


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _compute_expected_hours(self, contract, employee, date_from, date_to):
        """Compute expected working hours for the period based on resource calendar.
            Automatically ignores weekends, off-days, and company holidays."""
        calendar = contract.resource_calendar_id or employee.resource_calendar_id
        if not calendar:
            raise UserError(_("No working schedule defined for %s") % employee.name)

        total_hours = 0.0
        current_day = date_from

        while current_day <= date_to:
            # Calculate work hours for the day according to the resource calendar
            day_start = fields.Datetime.to_datetime(datetime.combine(current_day, datetime.min.time()))
            day_end = fields.Datetime.to_datetime(datetime.combine(current_day, datetime.max.time()))
            hours = calendar.get_work_hours_count(day_start, day_end)

            # Only add hours if calendar defines work for that day (weekends/off-days return 0)
            if hours > 0:
                total_hours += hours

            current_day += timedelta(days=1)

        return round(total_hours, 2)

    @api.model
    def _compute_attendance_hours(self, employee, date_from, date_to):
        """Compute effective worked hours for payroll period."""
        Attendance = self.env["hr.attendance"]
        contract = employee.contract_id
        if not contract:
            return 0.0, []

        calendar = contract.resource_calendar_id or employee.resource_calendar_id
        if not calendar:
            return 0.0, []

        # Limit period to contract active dates
        start_date = max(contract.date_start, date_from) if contract.date_start else date_from
        end_date = min(contract.date_end, date_to) if contract.date_end else date_to

        # Fetch all attendances within period
        attendances = Attendance.search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", start_date),
            ("check_in", "<=", end_date + timedelta(days=1))
        ])

        total_worked_hours = 0.0
        incomplete = []

        for att in attendances:
            if not att.check_out:
                incomplete.append(att)
                continue

            # Calculate scheduled hours for that attendance day
            att_date = att.check_in.date()
            day_start = fields.Datetime.to_datetime(datetime.combine(att_date, datetime.min.time()))
            day_end = fields.Datetime.to_datetime(datetime.combine(att_date, datetime.max.time()))
            day_work_hours = calendar.get_work_hours_count(day_start, day_end)

            if day_work_hours == 0:
                continue  # Skip weekends/off-days

            # Adjust hours for late / early
            is_late = getattr(att, 'is_late', False)
            is_early = getattr(att, 'is_early_checkout', False)

            if is_late and is_early and att.leave_id and att.early_checkout_leave_id:
                effective_hours = 0.0
            elif is_late and att.leave_id:
                effective_hours = day_work_hours / 2
            elif is_early and att.early_checkout_leave_id:
                effective_hours = day_work_hours / 2
            else:
                effective_hours = day_work_hours

            total_worked_hours += effective_hours

        return round(total_worked_hours, 2), incomplete

    @api.model
    def _get_leave_hours(self, employee, date_from, date_to):
        """Compute paid and unpaid leave hours based on leave type."""
        Leave = self.env["hr.leave"]
        leaves = Leave.search([
            ("employee_id", "=", employee.id),
            ("state", "=", "validate"),
            ("request_date_from", "<=", date_to),
            ("request_date_to", ">=", date_from),
        ])
        paid_hours = unpaid_hours = 0.0
        calendar = employee.contract_id.resource_calendar_id or employee.resource_calendar_id

        for leave in leaves:
            leave_type = leave.holiday_status_id
            # Calculate actual overlapping period
            start_date = max(date_from, leave.request_date_from)
            end_date = min(date_to, leave.request_date_to)

            current_day = start_date
            while current_day <= end_date:
                # Calculate only the overlapping segment for this day
                seg_start = max(
                    fields.Datetime.to_datetime(datetime.combine(current_day, datetime.min.time())),
                    leave.date_from,
                )
                seg_end = min(
                    fields.Datetime.to_datetime(datetime.combine(current_day, datetime.max.time())),
                    leave.date_to,
                )

                if seg_start < seg_end:
                    hours = calendar.get_work_hours_count(seg_start, seg_end)

                    if leave_type.name in ["Unpaid", "Unpaid Earned Leave"]:
                        unpaid_hours += hours
                    else:
                        paid_hours += hours

                current_day += timedelta(days=1)

        return paid_hours, unpaid_hours

    def _create_or_update_input(self, payslip, code, amount, contract):
        """Create or update input line for deduction."""
        line = payslip.input_line_ids.filtered(lambda l: l.code == code)
        if line:
            line.amount = amount
        else:
            salary_rule = self.env["hr.salary.rule"].search([("code", "=", code)], limit=1)
            payslip.line_ids = [(0, 0, {
                "name": salary_rule.name,
                "code": code,
                "category_id": salary_rule.category_id.id,
                "sequence": salary_rule.sequence or 100,
                "salary_rule_id": salary_rule.id,
                "contract_id": contract.id,
                "employee_id": payslip.employee_id.id,
                "amount": abs(amount),
                "quantity": 1,
                "rate": 100,
            })] + [(4, line.id) for line in payslip.line_ids]

    def compute_sheet(self):
        """Override compute sheet method for generation of payslips"""
        res = super().compute_sheet()
        for payslip in self:
            contract = payslip.contract_id
            if not contract:
                continue

            expected_hours = self._compute_expected_hours(contract, payslip.employee_id, payslip.date_from,
                                                          payslip.date_to)
            worked_hours, incomplete = self._compute_attendance_hours(payslip.employee_id, payslip.date_from,
                                                                      payslip.date_to)
            paid_hours, unpaid_hours = self._get_leave_hours(payslip.employee_id, payslip.date_from, payslip.date_to)

            if incomplete:
                raise UserError(_("Employee %s has incomplete attendances in period %s - %s") % (
                    payslip.employee_id.name, payslip.date_from, payslip.date_to))

            # Total missing hours = expected - (worked + paid leaves) + unpaid leaves
            effective_hours = worked_hours + paid_hours
            missing_hours = max(0.0, expected_hours - effective_hours)

            hourly_rate = contract.wage / expected_hours if expected_hours else 0.0
            deduction_amount = round(missing_hours * hourly_rate, 2)

            # Create a single Unpaid Attendance Deduction line
            if deduction_amount > 0:
                self._create_or_update_input(
                    payslip,
                    "ATT_UNPAID",
                    -deduction_amount,
                    contract
                )

            # inputs
            payslip.worked_days_line_ids = [(5, 0, 0)] + [
                (0, 0, line) for line in payslip.get_worked_day_lines(contract, payslip.date_from, payslip.date_to)
            ]
        return res

    def get_worked_day_lines(self, contracts, date_from, date_to):
        """Compute worked days, paid leave, unpaid leave lines for hr.payslip.worked_days."""
        res = []
        for contract in contracts:
            employee = contract.employee_id
            calendar = contract.resource_calendar_id or employee.resource_calendar_id
            hours_per_day = calendar.hours_per_day or 8.0

            worked_hours, _ = self._compute_attendance_hours(employee, date_from, date_to)
            paid_hours, unpaid_hours = self._get_leave_hours(employee, date_from, date_to)

            # Worked Days
            if worked_hours > 0:
                res.append({
                    'name': 'Worked Days',
                    'sequence': 1,
                    'code': 'WORK100',
                    'number_of_days': worked_hours / hours_per_day,
                    'number_of_hours': worked_hours,
                    'contract_id': contract.id,
                })

            # Paid Leave
            if paid_hours > 0:
                res.append({
                    'name': 'Paid Leave',
                    'sequence': 2,
                    'code': 'LEAVE_PAID',
                    'number_of_days': paid_hours / hours_per_day,
                    'number_of_hours': paid_hours,
                    'contract_id': contract.id,
                })

            # Unpaid Leave
            if unpaid_hours > 0:
                res.append({
                    'name': 'Unpaid Leave',
                    'sequence': 3,
                    'code': 'LEAVE_UNPAID',
                    'number_of_days': unpaid_hours / hours_per_day,
                    'number_of_hours': unpaid_hours,
                    'contract_id': contract.id,
                })

        return res
