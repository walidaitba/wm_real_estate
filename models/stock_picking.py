from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override validate button to handle apartment/store/équipement state when delivery is validated"""
        # Call super to validate the picking
        res = super(StockPicking, self).button_validate()

        # Check if this is a delivery picking from a sale order
        sale_orders = self.env['sale.order'].search([('delivery_picking_id', '=', self.id)])
        if sale_orders:
            for sale_order in sale_orders:
                # Check if this is a real estate order
                if sale_order.is_real_estate:
                    _logger.info("Validated delivery picking %s for real estate order %s",
                                self.name, sale_order.name)

                    # Update apartment states to sold if not already
                    apartments_updated = 0
                    stores_updated = 0

                    for line in sale_order.order_line:
                        # Handle apartments
                        if line.apartment_id and line.apartment_id.state != 'sold':
                            try:
                                # Mark apartment as sold
                                line.apartment_id.with_context(from_sale_order=True).write({
                                    'state': 'sold',
                                    'is_locked': False,
                                    'locked_by_order_id': False,
                                    'lock_date': False
                                })

                                # Update the product state with context to prevent infinite recursion
                                if line.product_id and line.product_id.product_tmpl_id.is_apartment:
                                    line.product_id.product_tmpl_id.with_context(from_apartment_update=True).apartment_state = 'sold'

                                    # Quantity management is now handled by Odoo's standard inventory management

                                # Log the state change
                                _logger.info("Apartment %s state changed to sold after delivery validation",
                                            line.apartment_id.name)

                                apartments_updated += 1
                            except Exception as e:
                                _logger.error("Failed to update apartment %s state: %s",
                                            line.apartment_id.name, str(e))

                        # Handle stores
                        elif line.product_id and line.product_id.product_tmpl_id.is_store:
                            store_product = line.product_id.product_tmpl_id

                            if store_product.apartment_state != 'sold':
                                try:
                                    # Mark store as sold
                                    store_product.with_context(from_sale_order=True).write({
                                        'apartment_state': 'sold',
                                        'is_locked': False,
                                        'locked_by_order_id': False,
                                    })

                                    # Quantity management is now handled by Odoo's standard inventory management

                                    # Log the state change
                                    _logger.info("Store %s state changed to sold after delivery validation",
                                                store_product.name)

                                    stores_updated += 1
                                except Exception as e:
                                    _logger.error("Failed to update store %s state: %s",
                                                store_product.name, str(e))

                        # Handle équipements
                        elif line.product_id and line.product_id.product_tmpl_id.is_equipement:
                            equipement_product = line.product_id.product_tmpl_id

                            if equipement_product.apartment_state != 'sold':
                                try:
                                    # Mark équipement as sold
                                    equipement_product.with_context(from_sale_order=True).write({
                                        'apartment_state': 'sold',
                                        'is_locked': False,
                                        'locked_by_order_id': False,
                                    })

                                    # Quantity management is now handled by Odoo's standard inventory management

                                    # Log the state change
                                    _logger.info("Équipement %s state changed to sold after delivery validation",
                                                equipement_product.name)

                                    stores_updated += 1  # Use same counter for simplicity
                                except Exception as e:
                                    _logger.error("Failed to update équipement %s state: %s",
                                                equipement_product.name, str(e))

                    # Log a message suggesting to create an invoice manually
                    _logger.info("Delivery validated for order %s. Invoice should be created manually.",
                                sale_order.name)

                    # Show a success message to the user
                    message = _("""
Delivery Completed

The delivery for order %s has been validated.
%s apartment(s) and %s store(s) have been marked as 'Sold'.

Next steps:
1. Create an invoice
2. Send the invoice to the customer
3. Record the payment when received
""") % (
    sale_order.name,
    apartments_updated,
    stores_updated
)

                    # Log the message
                    self.env['mail.message'].create({
                        'body': message,
                        'message_type': 'notification',
                        'subtype_id': self.env.ref('mail.mt_note').id,
                        'model': 'stock.picking',
                        'res_id': self.id,
                    })

        return res
