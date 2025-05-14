from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """Override post action to handle apartment state when invoice is posted"""
        # Call super to post the invoice
        res = super(AccountMove, self).action_post()

        # Check if this is a customer invoice from a sale order
        if self.move_type == 'out_invoice' and self.invoice_origin:
            # Find the related sale order
            sale_orders = self.env['sale.order'].search([('name', '=', self.invoice_origin)])

            for sale_order in sale_orders:
                # Check if this sale order has apartments
                if sale_order.has_apartment:
                    _logger.info("Posted invoice %s for sale order %s with apartments", self.name, sale_order.name)
                    # No state change yet, we'll wait for payment

        return res

    def _invoice_paid_hook(self):
        """Hook when invoice is paid to update apartment state"""
        res = super(AccountMove, self)._invoice_paid_hook()

        # Check if this is a customer invoice from a sale order
        if self.move_type == 'out_invoice' and self.invoice_origin:
            # Find the related sale order
            sale_orders = self.env['sale.order'].search([('name', '=', self.invoice_origin)])

            for sale_order in sale_orders:
                # Check if this sale order has apartments and is a real estate order
                if sale_order.has_apartment and sale_order.is_real_estate:
                    _logger.info("Invoice %s for real estate order %s with apartments is paid", self.name, sale_order.name)

                    # Case 1: This is a deposit invoice payment (10%)
                    if sale_order.deposit_invoice_id and sale_order.deposit_invoice_id.id == self.id:
                        _logger.info("Deposit invoice %s for reservation %s is paid", self.name, sale_order.name)

                        # If the order is in reservation state, confirm it automatically
                        if sale_order.state == 'reservation':
                            try:
                                # Confirm the order
                                sale_order.action_confirm()

                                # Show a success message to the user
                                message = _("""
Deposit Payment Received

The deposit payment for order %s has been received.
The order has been automatically confirmed and is now in 'Sale Order' state.
A delivery order for the handover has been created.

Next steps:
1. Schedule the handover of keys/documents
2. Validate the delivery when the handover is complete
3. Create and send the final invoice
""") % sale_order.name

                                # Log the message
                                self.env['mail.message'].create({
                                    'body': message,
                                    'message_type': 'notification',
                                    'subtype_id': self.env.ref('mail.mt_note').id,
                                    'model': 'sale.order',
                                    'res_id': sale_order.id,
                                })

                                _logger.info("Confirmed order %s after deposit payment", sale_order.name)
                            except Exception as e:
                                _logger.error("Failed to confirm order %s after deposit payment: %s", sale_order.name, str(e))

                    # Case 2: This is a final invoice payment (90%)
                    elif sale_order.state == 'sale' and sale_order.is_deposit_invoiced:
                        _logger.info("Final invoice %s for order %s is paid", self.name, sale_order.name)

                        # Update apartment states to sold if not already
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
                                    _logger.info("Apartment %s state changed to sold after final invoice payment",
                                                line.apartment_id.name)
                                except Exception as e:
                                    _logger.error("Failed to update apartment %s state: %s", line.apartment_id.name, str(e))

                        # Show a success message to the user
                        message = _("""
Final Payment Received

The final payment for order %s has been received.
All apartments in this order are now marked as 'Sold'.

The real estate transaction is now complete.
""") % sale_order.name

                        # Log the message
                        self.env['mail.message'].create({
                            'body': message,
                            'message_type': 'notification',
                            'subtype_id': self.env.ref('mail.mt_note').id,
                            'model': 'sale.order',
                            'res_id': sale_order.id,
                        })

        return res
