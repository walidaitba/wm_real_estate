from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Real Estate fields
    project_id = fields.Many2one('real.estate.project', string='Project',
                                help="Related real estate project for this invoice")
    building_id = fields.Many2one('real.estate.building', string='Building',
                                 help="Related building for this invoice")

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
                    # Set project and building from sale order
                    if sale_order.project_id:
                        self.project_id = sale_order.project_id.id
                    # Get building from first line with apartment
                    for line in sale_order.order_line:
                        if line.building_id:
                            self.building_id = line.building_id.id
                            break

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

                    # Check if all invoices for this sale order are paid
                    all_invoices_paid = sale_order._check_all_invoices_paid()

                    # If all invoices are paid, mark apartments/stores as sold
                    if all_invoices_paid:
                        _logger.info("All invoices for order %s are paid. Marking properties as sold.", sale_order.name)

                        # Update apartment/store states to sold if not already
                        properties_updated = 0

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

                                    # Log the state change
                                    _logger.info("Apartment %s state changed to sold after full payment",
                                                line.apartment_id.name)
                                    properties_updated += 1
                                except Exception as e:
                                    _logger.error("Failed to update apartment %s state: %s", line.apartment_id.name, str(e))

                            # Handle stores
                            elif line.product_id and line.product_id.product_tmpl_id.is_store and line.product_id.product_tmpl_id.apartment_state != 'sold':
                                try:
                                    # Mark store as sold
                                    line.product_id.product_tmpl_id.with_context(from_sale_order=True).write({
                                        'apartment_state': 'sold',
                                        'is_locked': False,
                                        'locked_by_order_id': False,
                                    })

                                    # Log the state change
                                    _logger.info("Store %s state changed to sold after full payment",
                                                line.product_id.product_tmpl_id.name)
                                    properties_updated += 1
                                except Exception as e:
                                    _logger.error("Failed to update store %s state: %s",
                                                line.product_id.product_tmpl_id.name, str(e))

                        if properties_updated > 0:
                            # Show a success message to the user
                            message = _("""
Payment Complete

All payments for order %s have been received.
All properties in this order are now marked as 'Sold'.

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
