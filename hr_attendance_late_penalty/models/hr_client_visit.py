from odoo import models, fields


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
