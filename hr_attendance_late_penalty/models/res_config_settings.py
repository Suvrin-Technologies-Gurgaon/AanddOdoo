
# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    late_penalty_days_count = fields.Integer(
        string="Allowed Late/Early Count",
        default=2,
        config_parameter="hr_attendance_late_penalty.late_penalty_days_count",
        help="How many late arrival or early departure permissions are allowed per month before a penalty leave is created."
    )
    penalty_leave_type_id = fields.Many2one(
        "hr.leave.type",
        string="Penalty Leave Type",
        config_parameter="hr_attendance_late_penalty.penalty_leave_type_id",
        help="Leave type to use when creating the half-day penalty leave."
    )
