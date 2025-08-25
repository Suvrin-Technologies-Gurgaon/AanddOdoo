# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.
{
    "name": "Base Whatsapp Integrations",
    "author": "Softhealer Technologies",
    "license": "OPL-1",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Extra Tools",
    "summary": "Whatsapp Integration App Sale Whatsapp Integration Purchase Whatsapp CRM Whatsup Invoice Whatsapp Integration Inventory Whatsapp Integration Odoo Inventory Whatsapp Integration Stock Whatsapp Integration Inventory Send Customer Whatsapp Stock Send Client Whatsapp Send Incoming Order Delivery Order Send Whatsapp Send Internal Transfer Client Whatsup connector odoo Sales Order Whatsapp Quotation Whatsapp Sale Order Whatsapp SO Whatsup Quotes Whatsapp chat customer whatsapp connector Quotation Diret Whatsapp Direct Sale Order Odoo Purchase Order Whatsapp PO Whatsapp Request For Quotation Whatsapp PO Whatsup Request For Quote Whatsapp RFQ whatsapp connector Rfq order whatsapp Purchase Order Whatsup Odoo Payslip Whatsapp Payroll Whatsapp Payslip Whatsup Payroll Whatsup Manage Whatsap Payslip whats app Odoo CRM Whatsapp Integration Opportunity whatsapp connector lead Whatsapp communication CRM Whatsup Integration Opportunity whatsup lead Whatsup chat Send Whatsapp Attachments odoo Accounting Whatsup payment whatsapp Invoice Whatsapp invoice whatsup Bill Whatsapp Credit Note whatsapp Invoice Details in whatsup Payment Whatsup account whatsup live whatsapp live chat whatsapp account Odoo whatsapp Integration Whatsapp Odoo Integration Odoo whatsup Integration Whatsup Odoo Integration",
    "description": """Using this module you can direct to Clients/Vendor's WhatsApp.""",
    "version": "0.0.1",
    "depends": ['base_setup', 'mail'],
    "application": True,
    "data": [
            "security/whatsapp_security.xml",
            "security/ir.model.access.csv",
            "views/res_users_inherit_view.xml",
            "wizard/send_whasapp_number_view.xml",
            "wizard/send_whatsapp_message_view.xml",
            "views/res_partner_views.xml",
            "views/mail_message.xml",

    ],

    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "price": 1,
    "currency": "EUR"
}
