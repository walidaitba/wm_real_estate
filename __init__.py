from . import models
from . import wizard

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def post_init_hook(cr, registry):
    """Post-init hook to update quantities for all apartments"""
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Get all available apartments
    apartments = env['real.estate.apartment'].search([('state', '=', 'available')])

    if apartments:
        _logger.info("Updating quantities for %s available apartments", len(apartments))

        # Update quantities for all available apartments
        for apartment in apartments:
            try:
                # Find all products linked to this apartment
                products = env['product.template'].search([('apartment_id', '=', apartment.id)])

                for product in products:
                    # Set quantity to 1 for available apartments
                    apartment._set_inventory_quantity(product, 1.0)
                    _logger.info("Updated quantity for apartment %s", apartment.name)
            except Exception as e:
                _logger.error("Error updating quantity for apartment %s: %s", apartment.name, str(e))

    # Get all non-available apartments
    apartments = env['real.estate.apartment'].search([('state', '!=', 'available')])

    if apartments:
        _logger.info("Updating quantities for %s non-available apartments", len(apartments))

        # Update quantities for all non-available apartments
        for apartment in apartments:
            try:
                # Find all products linked to this apartment
                products = env['product.template'].search([('apartment_id', '=', apartment.id)])

                for product in products:
                    # Set quantity to 0 for non-available apartments
                    apartment._set_inventory_quantity(product, 0.0)
                    _logger.info("Updated quantity for apartment %s", apartment.name)
            except Exception as e:
                _logger.error("Error updating quantity for apartment %s: %s", apartment.name, str(e))
