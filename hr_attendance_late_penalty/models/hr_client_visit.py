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
        ('rejected', 'Rejected')
    ], default='draft', string="Status", tracking=True)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

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
