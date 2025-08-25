from odoo import models, fields, api
import requests


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    check_in_address = fields.Char(string="Check-in Address")
    check_out_address = fields.Char(string="Check-out Address")

    @api.model
    def create(self, vals):
        res = super(HrAttendance, self).create(vals)
        if res.check_in and res.in_latitude and res.in_longitude:
            res._get_address_from_coords('in')
        return res

    def write(self, vals):
        res = super(HrAttendance, self).write(vals)
        if 'in_latitude' in vals or 'in_longitude' in vals:
            self._get_address_from_coords('in')
        if 'out_latitude' in vals or 'out_longitude' in vals:
            self._get_address_from_coords('out')
        return res

    def _get_address_from_coords(self, check_type):
        for attendance in self:
            lat_field = f'{check_type}_latitude'
            lon_field = f'{check_type}_longitude'
            address_field = f'check_{check_type}_address'

            latitude = getattr(attendance, lat_field)
            longitude = getattr(attendance, lon_field)

            if latitude and longitude:
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
                try:
                    response = requests.get(url, headers={'User-Agent': 'Odoo HR Attendance'})
                    response.raise_for_status()
                    data = response.json()
                    address = data.get('display_name', 'Address not found')
                except requests.RequestException as e:
                    address = f"Error fetching address: {str(e)}"

                setattr(attendance, address_field, address)

    @api.model
    def _update_check_out_address(self):
        attendances = self.search([('check_out', '!=', False), ('check_out_address', '=', False)])
        for attendance in attendances:
            attendance._get_address_from_coords('out')