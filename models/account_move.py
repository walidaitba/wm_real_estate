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
                # Check if this sale order has apartments and is a real estate order
                if sale_order.has_apartment and sale_order.is_real_estate:
                    _logger.info("Posted invoice %s for sale order %s with apartments", self.name, sale_order.name)
                    
                    # Set project and building from sale order
                    if sale_order.project_id:
                        self.project_id = sale_order.project_id.id
                    # Get building from first line with apartment
                    for line in sale_order.order_line:
                        if line.building_id:
                            self.building_id = line.building_id.id
                            break
                    
                    # *** NEW LOGIC FOR AUTO WORKFLOW ***
                    # Since auto workflow skips delivery and goes directly to invoice creation,
                    # mark apartments/stores as sold immediately when invoice is posted
                    # (regardless of payment status)
                    self._mark_properties_as_sold_on_invoice_creation(sale_order)

        return res

    def _mark_properties_as_sold_on_invoice_creation(self, sale_order):
        """Mark apartments/stores as sold when invoice is created (for auto workflow)"""
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
                    _logger.info("Apartment %s state changed to sold on invoice creation (auto workflow)",
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
                    _logger.info("Store %s state changed to sold on invoice creation (auto workflow)",
                                line.product_id.product_tmpl_id.name)
                    properties_updated += 1
                except Exception as e:
                    _logger.error("Failed to update store %s state: %s",
                                line.product_id.product_tmpl_id.name, str(e))

        if properties_updated > 0:
            # Post a message to the sale order
            message = _("""
Invoice Created - Properties Sold

Invoice %s has been created for order %s.
%s properties have been marked as 'Sold'.

Status updated automatically due to invoice creation (auto workflow).
""") % (self.name, sale_order.name, properties_updated)

            # Log the message to the sale order
            sale_order.message_post(
                body=message,
                message_type='notification',
                subtype_id=self.env.ref('mail.mt_note').id,
            )

            _logger.info("Marked %s properties as sold for order %s on invoice creation", 
                        properties_updated, sale_order.name)

    def _invoice_paid_hook(self):
        """Hook when invoice is paid - properties already marked as sold on invoice creation"""
        res = super(AccountMove, self)._invoice_paid_hook()

        # Check if this is a customer invoice from a sale order
        if self.move_type == 'out_invoice' and self.invoice_origin:
            # Find the related sale order
            sale_orders = self.env['sale.order'].search([('name', '=', self.invoice_origin)])

            for sale_order in sale_orders:
                # Check if this sale order has apartments and is a real estate order
                if sale_order.has_apartment and sale_order.is_real_estate:
                    _logger.info("Invoice %s for real estate order %s with apartments is paid", self.name, sale_order.name)

                    # Properties are already marked as sold on invoice creation
                    # Just log a payment confirmation message
                    message = _("""
Payment Received

Payment for invoice %s has been received.
Properties were already marked as 'Sold' when the invoice was created.

The real estate transaction is now complete with payment confirmed.
""") % self.name

                    # Log the message to the sale order
                    sale_order.message_post(
                        body=message,
                        message_type='notification',
                        subtype_id=self.env.ref('mail.mt_note').id,
                    )

        return res
