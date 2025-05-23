from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    cin = fields.Char(
        string='CIN',
        help='Carte d\'Identité Nationale',
        tracking=True,  # Enable tracking for audit purposes
        index=True,    # Index the field for better search performance
        copy=False     # Don't copy this field when duplicating records
    )
