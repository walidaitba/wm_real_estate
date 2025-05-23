from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    cin = fields.Char(
        string='CIN',
        help='Carte d\'Identité Nationale',
        related='partner_id.cin',  # Link to the partner's CIN
        store=True,               # Store for better performance
        readonly=False           # Allow editing through user form
    )
