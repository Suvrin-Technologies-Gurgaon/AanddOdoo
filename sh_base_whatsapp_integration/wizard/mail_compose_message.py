# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields
from odoo.tools import html2plaintext


class Message(models.TransientModel):
    _inherit = "mail.compose.message"

    is_wp = fields.Boolean("Is whatsapp ?")

    def action_send_wp(self):
        text = html2plaintext(self.body)
        phone = self.partner_ids.mobile
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        if self.attachment_ids:
            text += "%0A%0A Other Attachments :"
            for attachment in self.attachment_ids:
                attachment.generate_access_token()
                text += "%0A%0A"
                text += (
                    base_url
                    + "/web/content/ir.attachment/"
                    + str(attachment.id)
                    + "/datas?access_token="
                    + attachment.access_token
                )
        context = dict(self._context or {})
        active_id = context.get("active_id", False)
        active_model = context.get("active_model", False)
        if text and active_id and active_model:
            message = (
                str(text)
                .replace("*", "")
                .replace("_", "")
                .replace("%0A", "<br/>")
                .replace("%20", " ")
                .replace("%26", "&")
            )
            if (
                active_model == "sale.order"
                and self.env["sale.order"]
                .browse(active_id)
                .company_id.display_in_message
            ):
                self.env["mail.message"].create(
                    {
                        "partner_ids": [(6, 0, self.partner_ids.ids)] or False,
                        "model": "sale.order",
                        "res_id": active_id,
                        "author_id": self.env.user.partner_id.id or False,
                        "body": message or False,
                        "message_type": "comment",
                    }
                )
            if (
                active_model == "purchase.order"
                and self.env["purchase.order"]
                .browse(active_id)
                .company_id.purchase_display_in_message
            ):
                self.env["mail.message"].create(
                    {
                        "partner_ids": [(6, 0, self.partner_ids.ids)] or False,
                        "model": "purchase.order",
                        "res_id": active_id,
                        "author_id": self.env.user.partner_id.id or False,
                        "body": message or False,
                        "message_type": "comment",
                    }
                )
            if (
                active_model == "account.move"
                and self.env["account.move"]
                .browse(active_id)
                .company_id.invoice_display_in_message
                or active_model == "account.payment"
                and self.env["account.payment"]
                .browse(active_id)
                .company_id.invoice_display_in_message
            ):
                self.env["mail.message"].create(
                    {
                        "partner_ids": [(6, 0, self.partner_ids.ids)] or False,
                        "model": active_model,
                        "res_id": active_id,
                        "author_id": self.env.user.partner_id.id or False,
                        "body": message or False,
                        "message_type": "comment",
                    }
                )

            if (
                active_model == "stock.picking"
                and self.env["stock.picking"]
                .browse(active_id)
                .company_id.inventory_display_in_message
            ):
                self.env["mail.message"].create(
                    {
                        "partner_ids": [(6, 0, self.partner_ids.ids)] or False,
                        "model": "stock.picking",
                        "res_id": active_id,
                        "author_id": self.env.user.partner_id.id or False,
                        "body": message or False,
                        "message_type": "comment",
                    }
                )

            if (active_model == "hr.payslip"
                and self.env["hr.payslip"]
                .browse(active_id)
                .company_id.payroll_information_in_message
            ):
                employee = self.env["hr.payslip"].browse(active_id).employee_id
                phone = self.env["hr.payslip"].browse(active_id).employee_id.mobile
                                
                self.env["mail.message"].create(
                {
                    "partner_ids": [4, employee.work_contact_id.id] if employee.work_contact_id else None,
                    "model": "hr.payslip",
                    "res_id": active_id,
                    "author_id": self.env.user.partner_id.id or False,
                    "body": message or False,
                    "message_type": "comment",
                })

            if (
                active_model == "crm.lead"
                and self.env["crm.lead"]
                .browse(active_id)
                .company_id.crm_lead_display_in_message
            ):
                self.env["mail.message"].create(
                    {
                        "partner_ids": [(6, 0, self.partner_ids.ids)] or False,
                        "model": "crm.lead",
                        "res_id": active_id,
                        "author_id": self.env.user.partner_id.id or False,
                        "body": message or False,
                        "message_type": "comment",
                    }
                )

        return {
            "type": "ir.actions.act_url",
            "url": "https://web.whatsapp.com/send?l=&phone=" + phone + "&text=" + text,
            "target": "new",
        }
