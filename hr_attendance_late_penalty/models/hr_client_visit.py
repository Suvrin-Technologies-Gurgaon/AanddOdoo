from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError


class HrClientVisit(models.Model):
    _name = "hr.client.visit"
    _description = "Client Visit"
    _rec_name = 'purpose'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True,
                                  default=lambda self: self.env.user.employee_id)
    start_time = fields.Datetime("Start Time", required=True, tracking=True)
    end_time = fields.Datetime("End Time", required=True, tracking=True)
    client_name = fields.Char("Client Name", required=True, tracking=True)
    location = fields.Char("Location", tracking=True)
    purpose = fields.Text("Purpose", tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancel', 'Cancel')
    ], default='draft', string="Status", tracking=True)
    calendar_event_id = fields.Many2one('calendar.event', string="Calendar Event")

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_cancel_client_visit(self):
        """Method to cancel client visit"""
        for rec in self:
            rec.state = "cancel"
            if rec.calendar_event_id:
                rec.calendar_event_id.unlink()

    def action_approve(self):
        """Method to approve local visit"""
        for rec in self:
            rec.state = "approved"
            if not rec.calendar_event_id:
                event = self.env["calendar.event"].create({
                    "name": rec.purpose,
                    "start": rec.start_time,
                    "stop": rec.end_time,
                    "user_id": rec.employee_id.user_id.id or self.env.uid,
                    "partner_ids": [
                        (6, 0, [rec.employee_id.user_id.partner_id.id])] if rec.employee_id.user_id else False,
                })
                rec.calendar_event_id = event.id

    def action_reject(self):
        self.write({'state': 'rejected'})

    @api.constrains('start_time', 'end_time')
    def _check_validations_date(self):
        for rec in self:
            if not rec.start_time or not rec.end_time:
                continue

            start_date = rec.start_time.date()
            end_date = rec.end_time.date()
            if end_date < start_date:
                raise ValidationError("End date must be greater than Start date.")

            today = fields.Date.context_today(rec)
            if start_date < today:
                raise ValidationError("Start date cannot be in the past.")
