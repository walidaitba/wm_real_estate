from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override validate button to handle apartment state when delivery is validated"""
        # Call super to validate the picking
        res = super(StockPicking, self).button_validate()

        # Check if this is a delivery picking from a sale order
        sale_orders = self.env['sale.order'].search([('delivery_picking_id', '=', self.id)])
        if sale_orders:
            for sale_order in sale_orders:
                # Check if this sale order has apartments and is a real estate order
                if sale_order.has_apartment and sale_order.is_real_estate:
                    _logger.info("Validated delivery picking %s for real estate order %s with apartments",
                                self.name, sale_order.name)

                    # Update apartment states to sold if not already
                    apartments_updated = 0
                    for line in sale_order.order_line:
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

                                    # Ensure inventory quantity is updated
                                    line.product_id.product_tmpl_id._update_inventory_quantity()

                                # Log the state change
                                _logger.info("Apartment %s state changed to sold after delivery validation",
                                            line.apartment_id.name)

                                apartments_updated += 1
                            except Exception as e:
                                _logger.error("Failed to update apartment %s state: %s",
                                            line.apartment_id.name, str(e))

                    # Log a message suggesting to create an invoice manually
                    _logger.info("Delivery validated for order %s. Invoice should be created manually.",
                                sale_order.name)

                    # Show a success message to the user
                    message = _("""
Delivery Completed

The delivery for order %s has been validated.
%s apartment(s) have been marked as 'Sold'.

Next steps:
1. Create an invoice
2. Send the invoice to the customer
3. Record the payment when received
""") % (
    sale_order.name,
    apartments_updated
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
