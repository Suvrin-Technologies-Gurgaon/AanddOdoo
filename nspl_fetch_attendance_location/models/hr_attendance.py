from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)


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
            if check_type == "in":
                latitude = attendance.in_latitude
                longitude = attendance.in_longitude
            if check_type == "out":
                latitude = attendance.out_latitude
                longitude = attendance.out_longitude
            # url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
            # headers = {'User-Agent': 'Location Checker'}
            #
            # response = requests.get(url, headers=headers)
            # data = response.json()
            # print("uuuuuuuuuuuuuuu",data['display_name'])
            # add = requests.get("https://api.ipify.org").text
            # url = "https://get.geojs.io/v1/ip/geo/" + add + ".json"
            # geo_request = requests.get(url)
            # geo_data = geo_request.json()
            # print(geo_request)
            # print(geo_data)
            # _logger.info("latitude..........%s", latitude)






            # latitude = getattr(attendance, lat_field)
            # longitude = getattr(attendance, lon_field)
            _logger.info("latitude...............%s", latitude)
            _logger.info("longitude............................................................%s", longitude)

            if latitude and longitude:
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
                _logger.info("url............................................................%s", url)

                try:
                    response = requests.get(url, headers={'User-Agent': 'Odoo HR Attendance'})
                    _logger.info("response............................................................%s", response)

                    response.raise_for_status()
                    data = response.json()
                    _logger.info("data............................................................%s", data)

                    address = data.get('display_name', 'Address not found')
                    _logger.info("address............................................................%s", address)

                except requests.RequestException as e:
                    address = f"Error fetching address: {str(e)}"

                setattr(attendance, address_field, address)

    @api.model
    def _update_check_out_address(self):
        attendances = self.search([('check_out', '!=', False), ('check_out_address', '=', False)])
        for attendance in attendances:
            attendance._get_address_from_coords('out')