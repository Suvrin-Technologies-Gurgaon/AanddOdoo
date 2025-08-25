from odoo import models, fields

class Employee(models.Model):
    _inherit = 'hr.employee'

    department_ids = fields.Many2many(
        'hr.department',
        'employee_multi_department_rel',
        'employee_id',
        'department_id',
        string="Departments"
    )
