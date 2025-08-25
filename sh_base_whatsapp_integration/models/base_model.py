# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    sign = fields.Text('Signature')
