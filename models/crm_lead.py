from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # Real Estate specific fields
    property_type = fields.Selection([
        ('apartment', 'Appartement'),
        ('store', 'Magasin')
    ], string='Type de propriété', help="Type de propriété que le client recherche")

    building_id = fields.Many2one('real.estate.building', string='Bâtiment',
                                 help="Bâtiment où se trouve la propriété")

    project_id = fields.Many2one(related='building_id.project_id', string='Projet',
                                store=True, readonly=True)

    apartment_id = fields.Many2one('real.estate.apartment', string='Appartement',
                                  domain="[('state', '=', 'available'), ('building_id', '=', building_id)]",
                                  help="Appartement que le client recherche")

    store_product_id = fields.Many2one('product.template', string='Magasin',
                                     domain="[('is_store', '=', True), ('apartment_state', '=', 'available'), ('building_id', '=', building_id)]",
                                     help="Magasin que le client recherche")

    # No reservation-related fields needed

    @api.onchange('property_type')
    def _onchange_property_type(self):
        """When property type changes, reset the property selection"""
        self.apartment_id = False
        self.store_product_id = False

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """When building changes, reset the property selection"""
        self.apartment_id = False
        self.store_product_id = False

    # No reservation methods needed
