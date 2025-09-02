from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    @api.model
    def _generate_monthly_payslips(self):
        """Generate payroll batch and compute for all active employees on last working day."""
        Employee = self.env["hr.employee"].search([("active", "=", True)])
        if not Employee:
            return

        today = date.today()
        first_day = today.replace(day=1)
        last_day = (first_day + relativedelta(months=1)) - timedelta(days=1)

        # If last day is weekend, move to previous Friday
        if last_day.weekday() > 4:  # Saturday/Sunday
            last_day -= timedelta(days=last_day.weekday() - 4)

        # Create payslip batch
        payslip_run = self.create({
            "name": "Payroll %s" % first_day.strftime("%B %Y"),
            "date_start": first_day,
            "date_end": last_day,
        })

        # Generate payslips for all employees
        for emp in Employee:
            contract = emp.contract_id
            if not contract or not contract.struct_id:
                continue  # Skip employees without contract or structure

            payslip_name = "Payslip %s / %s" % (first_day.strftime("%B %Y"), emp.name)
            payslip = self.env["hr.payslip"].create({
                "name": payslip_name,
                "employee_id": emp.id,
                "contract_id": contract.id,
                "struct_id": contract.struct_id.id,
                "date_from": first_day,
                "date_to": last_day,
                "payslip_run_id": payslip_run.id,
            })
            payslip.compute_sheet()
