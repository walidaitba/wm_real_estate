from . import models
from . import wizard

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def post_init_hook(cr, registry):
    """Post-init hook for module initialization"""
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Log the number of apartments and products
    apartment_count = env['real.estate.apartment'].search_count([])
    product_count = env['product.template'].search_count([('is_apartment', '=', True)])
    store_count = env['product.template'].search_count([('is_store', '=', True)])

    _logger.info("Module initialized with %s apartments, %s apartment products, and %s store products",
                apartment_count, product_count, store_count)

    # Quantity management is now handled by Odoo's standard inventory management
