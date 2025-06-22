from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    apartment_id = fields.Many2one('real.estate.apartment', string='Apartment')
    apartment_state = fields.Selection(related='apartment_id.state', string='Apartment Status', readonly=True)
    building_id = fields.Many2one('real.estate.building', string='Building')

    # Computed field to show apartment status including locked state
    apartment_status = fields.Selection([
        ('disponible', 'Disponible'),
        ('in_quotation', 'In Quotation'),  # This represents the locked state
        ('prereserved', 'Préréservé'),
        ('sold', 'Vendu'),
    ], string='Status', compute='_compute_apartment_status', store=True)

    @api.depends('apartment_id', 'apartment_id.state', 'apartment_id.is_locked', 'product_id', 'product_id.product_tmpl_id.apartment_state', 'product_id.product_tmpl_id.is_locked')
    def _compute_apartment_status(self):
        """Compute the status to display in the UI, including locked state for both apartments and stores"""
        for line in self:
            if line.apartment_id:
                # Handle apartments
                if line.apartment_id.state == 'disponible' and line.apartment_id.is_locked:
                    line.apartment_status = 'in_quotation'
                else:
                    line.apartment_status = line.apartment_id.state
            elif line.product_id and line.product_id.product_tmpl_id.is_store:
                # Handle stores
                store_product = line.product_id.product_tmpl_id
                if store_product.apartment_state == 'disponible' and store_product.is_locked:
                    line.apartment_status = 'in_quotation'
                else:
                    line.apartment_status = store_product.apartment_state
            else:
                line.apartment_status = False

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """When building is selected, filter apartments"""
        if self.building_id:
            # If we have a building, filter apartments by this building and show only disponible (exclude blocker)
            return {'domain': {'apartment_id': [('building_id', '=', self.building_id.id), ('state', '=', 'disponible')]}}
        elif self.order_id.project_id:
            # If we have a project but no building, filter apartments by project (exclude blocker)
            return {'domain': {'apartment_id': [('project_id', '=', self.order_id.project_id.id), ('state', '=', 'disponible')]}}
        else:
            # No filters except state (exclude blocker)
            return {'domain': {'apartment_id': [('state', '=', 'disponible')]}}

    @api.onchange('apartment_id')
    def _onchange_apartment_id(self):
        """When apartment is selected, set building and product"""
        if self.apartment_id:
            # Set the building
            self.building_id = self.apartment_id.building_id.id

            # Find the product linked to this apartment
            product = self.env['product.template'].search([
                ('apartment_id', '=', self.apartment_id.id),
                ('is_apartment', '=', True)
            ], limit=1)

            if product and product.product_variant_id:
                self.product_id = product.product_variant_id.id

            # Generate description for the apartment
            self._generate_apartment_description()

    def _generate_apartment_description(self):
        """Generate a detailed description for the apartment"""
        if self.apartment_id:
            apartment = self.apartment_id
            # Get all relevant apartment details
            project_name = apartment.project_id.name if apartment.project_id else "N/A"
            building_name = apartment.building_id.name if apartment.building_id else "N/A"
            area = apartment.area if apartment.area else "N/A"
            
            # Check if it's an apartment product to include floor, rooms, and bathrooms
            product = self.product_id.product_tmpl_id if self.product_id else False
            is_apartment = product and product.is_apartment if product else True  # Default to True if no product
            
            # Base description for all property types
            property_details = f"""
Projet: {project_name}
Bâtiment: {building_name}
Appartement: {apartment.name}
"""
            
            # Add floor, rooms, and bathrooms only for apartments
            if is_apartment:
                floor = apartment.floor if apartment.floor is not None else "N/A"
                rooms = apartment.rooms if apartment.rooms else "N/A"
                bathrooms = apartment.bathrooms if apartment.bathrooms else "N/A"
                
                property_details += f"""Étage: {floor}
Pièces: {rooms}
Salles de bain: {bathrooms}
"""
            
            # Add surface for all property types
            property_details += f"Surface: {area} m²"
            
            self.name = property_details

    @api.onchange('product_id')
    def _onchange_product_id_apartment(self):
        """When product is selected, check if it's an apartment and set apartment_id"""
        if self.product_id and self.product_id.product_tmpl_id.is_apartment:
            # Find the apartment linked to this product
            apartment = self.env['real.estate.apartment'].search([
                ('product_tmpl_ids', 'in', self.product_id.product_tmpl_id.id)
            ], limit=1)
            if apartment:
                self.apartment_id = apartment.id
                self.building_id = apartment.building_id.id
                # Generate description for the apartment
                self._generate_apartment_description()

    @api.model
    def create(self, vals):
        """Override create to handle apartment/store/équipement locking"""
        # Make sure name is set for the sale order line
        if not vals.get('name') and vals.get('product_id'):
            product = self.env['product.product'].browse(vals.get('product_id'))
            product_tmpl = product.product_tmpl_id if product else False

            if product_tmpl:
                # Handle apartments
                if product_tmpl.is_apartment:
                    # Find the apartment linked to this product
                    apartment = self.env['real.estate.apartment'].search([
                        ('product_tmpl_ids', 'in', product_tmpl.id)
                    ], limit=1)

                    if apartment:
                        # Generate a description for the apartment
                        project_name = apartment.project_id.name if apartment.project_id else "N/A"
                        building_name = apartment.building_id.name if apartment.building_id else "N/A"
                        area = apartment.area if apartment.area else "N/A"
                        
                        # Base description for all property types
                        property_details = f"""
Projet: {project_name}
Bâtiment: {building_name}
Appartement: {apartment.name}
"""
                        
                        # Add floor, rooms, and bathrooms only for apartments
                        if product_tmpl.is_apartment:
                            floor = apartment.floor if apartment.floor is not None else "N/A"
                            rooms = apartment.rooms if apartment.rooms else "N/A"
                            bathrooms = apartment.bathrooms if apartment.bathrooms else "N/A"
                            
                            property_details += f"""Étage: {floor}
Pièces: {rooms}
Salles de bain: {bathrooms}
"""
                        
                        # Add surface for all property types
                        property_details += f"Surface: {area} m²"
                        
                        vals['name'] = property_details
                        # Also set the apartment_id and building_id
                        vals['apartment_id'] = apartment.id
                        vals['building_id'] = apartment.building_id.id

                # Handle stores
                elif product_tmpl.is_store:
                    # Generate a description for the store
                    project_name = product_tmpl.project_id.name if product_tmpl.project_id else "N/A"
                    building_name = product_tmpl.building_id.name if product_tmpl.building_id else "N/A"
                    area = product_tmpl.area if product_tmpl.area else "N/A"

                    vals['name'] = f"""
Projet: {project_name}
Bâtiment: {building_name}
Magasin: {product_tmpl.name}
Surface: {area} m²
"""
                    # Set the building_id
                    if product_tmpl.building_id:
                        vals['building_id'] = product_tmpl.building_id.id
                    
                    # Set quantity to surface area for stores (surface × price per m²)
                    if product_tmpl.area and not vals.get('product_uom_qty'):
                        vals['product_uom_qty'] = product_tmpl.area

                # Handle équipements
                elif product_tmpl.is_equipement:
                    # Generate a description for the équipement
                    project_name = product_tmpl.project_id.name if product_tmpl.project_id else "N/A"
                    building_name = product_tmpl.building_id.name if product_tmpl.building_id else "N/A"
                    area = product_tmpl.area if product_tmpl.area else "N/A"

                    vals['name'] = f"""
Projet: {project_name}
Bâtiment: {building_name}
Équipement: {product_tmpl.name}
Surface: {area} m²
"""
                    # Set the building_id
                    if product_tmpl.building_id:
                        vals['building_id'] = product_tmpl.building_id.id

        # Create the sale order line
        res = super(SaleOrderLine, self).create(vals)

        # If this is an apartment product, mark it as prereserved
        if res.product_id and res.product_id.product_tmpl_id.is_apartment:
            # Find the apartment linked to this product
            apartment = self.env['real.estate.apartment'].search([
                ('product_tmpl_ids', 'in', res.product_id.product_tmpl_id.id)
            ], limit=1)

            if apartment and apartment.state == 'disponible':
                # Check if apartment is already prereserved by another order
                if apartment.state == 'prereserved' or (apartment.is_locked and apartment.locked_by_order_id.id != res.order_id.id):
                    # If locked by another order that is not cancelled, raise an error
                    if apartment.locked_by_order_id and apartment.locked_by_order_id.state not in ['cancel']:
                        raise UserError(_("This apartment is currently reserved by another quotation. Please select another apartment."))

                # Mark the apartment as prereserved when added to quotation
                apartment.write({
                    'state': 'prereserved',
                    'is_locked': True,
                    'locked_by_order_id': res.order_id.id,
                    'lock_date': fields.Datetime.now()
                })

                # Update the product state with context to prevent infinite recursion
                if apartment.product_tmpl_ids:
                    for product in apartment.product_tmpl_ids:
                        # Update both state and lock status
                        product.with_context(from_apartment_update=True).write({
                            'apartment_state': 'prereserved',
                            'is_locked': True
                        })

                # Set the apartment_id field if not already set
                if not res.apartment_id:
                    res.apartment_id = apartment.id

                # Log the state change
                _logger.info("Apartment %s marked as prereserved for quotation %s",
                            apartment.name, res.order_id.name)

        # If this is a store product, mark it as prereserved
        elif res.product_id and res.product_id.product_tmpl_id.is_store:
            store_product = res.product_id.product_tmpl_id

            if store_product.apartment_state == 'disponible':
                # Update the store to prereserved state when added to quotation
                store_product.with_context(from_sale_order=True).write({
                    'apartment_state': 'prereserved',
                    'is_locked': True,
                    'locked_by_order_id': res.order_id.id,
                })

                # Log the state change
                _logger.info("Store %s marked as prereserved for quotation %s",
                            store_product.name, res.order_id.name)

        # If this is an équipement product, mark it as prereserved
        elif res.product_id and res.product_id.product_tmpl_id.is_equipement:
            equipement_product = res.product_id.product_tmpl_id

            if equipement_product.apartment_state == 'disponible':
                # Update the équipement to prereserved state when added to quotation
                equipement_product.with_context(from_sale_order=True).write({
                    'apartment_state': 'prereserved',
                    'is_locked': True,
                    'locked_by_order_id': res.order_id.id,
                })

                # Log the state change
                _logger.info("Équipement %s marked as prereserved for quotation %s",
                            equipement_product.name, res.order_id.name)

        return res

    def unlink(self):
        """Override unlink to handle apartment/store/équipement unlocking"""
        for line in self:
            # Handle apartments
            if line.apartment_id and line.apartment_id.is_locked and line.apartment_id.locked_by_order_id.id == line.order_id.id:
                # Unlock apartment when removed from sale order and set state back to disponible
                line.apartment_id.write({
                    'is_locked': False,
                    'locked_by_order_id': False,
                    'lock_date': False,
                    'state': 'disponible'
                })

                # Update the product state with context to prevent infinite recursion
                if line.apartment_id.product_tmpl_ids:
                    for product in line.apartment_id.product_tmpl_ids:
                        product.with_context(from_apartment_update=True).apartment_state = 'disponible'

                # Log the unlocking
                _logger.info("Apartment %s unlocked when removed from quotation %s",
                            line.apartment_id.name, line.order_id.name)

            # Handle stores
            elif line.product_id and line.product_id.product_tmpl_id.is_store:
                store_product = line.product_id.product_tmpl_id

                # Only unlock stores that are locked by this order
                if store_product.is_locked and store_product.locked_by_order_id.id == line.order_id.id:
                    # Reset store state to disponible
                    store_product.with_context(from_sale_order=True).write({
                        'apartment_state': 'disponible',
                        'is_locked': False,
                        'locked_by_order_id': False,
                    })

                    # Log the state change
                    _logger.info("Store %s state changed back to disponible when removed from quotation %s",
                                store_product.name, line.order_id.name)

            # Handle équipements
            elif line.product_id and line.product_id.product_tmpl_id.is_equipement:
                equipement_product = line.product_id.product_tmpl_id

                # Only unlock équipements that are locked by this order
                if equipement_product.is_locked and equipement_product.locked_by_order_id.id == line.order_id.id:
                    # Reset équipement state to disponible
                    equipement_product.with_context(from_sale_order=True).write({
                        'apartment_state': 'disponible',
                        'is_locked': False,
                        'locked_by_order_id': False,
                    })

                    # Log the state change
                    _logger.info("Équipement %s state changed back to disponible when removed from quotation %s",
                                equipement_product.name, line.order_id.name)

        return super(SaleOrderLine, self).unlink()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_real_estate = fields.Boolean(string='Real Estate', default=False,
                                   help="Indicates if this is a real estate sale/reservation")
    has_apartment = fields.Boolean(string='Has Apartment', compute='_compute_has_apartment', store=True,
                                  help="Technical field to indicate if the order contains an apartment")
    project_id = fields.Many2one('real.estate.project', string='Project',
                                help="Select the real estate project for this reservation")
    has_project = fields.Boolean(string='Has Project', compute='_compute_has_project', store=True,
                               help="Technical field to indicate if a project is selected")
    project_readonly = fields.Boolean(string='Project Readonly', default=False,
                                    help="Technical field to make project field readonly based on context")
    is_tbd_customer = fields.Boolean(string='Is TBD Customer', compute='_compute_is_tbd_customer', store=True,
                                   help="Technical field to indicate if the partner is the TBD Customer")

    # Real Estate specific fields
    is_deposit_invoiced = fields.Boolean(string='Deposit Invoiced', default=False,
                                       help="Indicates if the deposit invoice has been created")
    deposit_amount = fields.Monetary(string='Deposit Amount', compute='_compute_deposit_amount', store=True,
                                   help="Amount of the deposit (10% of total)")
    deposit_invoice_id = fields.Many2one('account.move', string='Deposit Invoice',
                                       help="Link to the deposit invoice")
    deposit_invoice_state = fields.Selection(related='deposit_invoice_id.payment_state',
                                          string='Deposit Invoice Status',
                                          help="Payment status of the deposit invoice")

    # Fields for delivery
    delivery_picking_id = fields.Many2one('stock.picking', string='Delivery Order',
                                        help="Link to the delivery order")
    delivery_state = fields.Selection(related='delivery_picking_id.state',
                                    string='Delivery Status',
                                    help="Status of the delivery order")

    # We no longer need a custom reservation state - using standard Odoo states



    @api.model
    def default_get(self, fields_list):
        """Override default_get to set project_readonly from context"""
        res = super(SaleOrder, self).default_get(fields_list)

        # Set project_readonly from context
        if self.env.context.get('default_project_readonly'):
            res['project_readonly'] = True

        # Set is_real_estate to True by default
        if 'is_real_estate' in fields_list and not res.get('is_real_estate'):
            res['is_real_estate'] = True

        return res

    # Override the _check_partner_id constraint to make partner_id optional for draft real estate orders
    @api.constrains('partner_id', 'state', 'is_real_estate')
    def _check_partner_id(self):
        """Check that partner_id is set for non-draft orders and non-real estate orders"""
        for order in self:
            # Skip the check for draft real estate orders
            if order.is_real_estate and order.state == 'draft':
                continue

            # For all other cases, partner_id is required
            if not order.partner_id:
                raise ValidationError(_("Customer is required for this order."))

    @api.model
    def create(self, vals):
        """Override create to handle orders without partner_id for apartment reservations"""
        # If this is a real estate order with order lines but no partner_id,
        # we'll create it as a draft order that will be completed later
        if vals.get('is_real_estate') and vals.get('order_line') and not vals.get('partner_id'):
            # Log that we're creating a draft order without a partner
            _logger.info("Creating draft real estate order without partner")

            # Set state to draft explicitly
            vals['state'] = 'draft'

            # Set a temporary partner_id to bypass Odoo's constraint
            # We'll use a special partner that represents "To be determined"
            tbd_partner = self.env['res.partner'].search([('name', '=', 'TBD Customer')], limit=1)
            if not tbd_partner:
                # Create the TBD partner if it doesn't exist
                partner_vals = {
                    'name': 'TBD Customer',
                    'comment': 'This is a temporary customer used for draft real estate orders. Please select a real customer before confirming the order.',
                    'active': True,
                    'type': 'contact',  # Explicitly set the type to 'contact'
                }
                
                # Create the partner with a clean context to avoid inheriting unwanted values
                tbd_partner = self.env['res.partner'].with_context(clean_context=True).create(partner_vals)
                _logger.info("Created TBD Customer partner for draft real estate orders")

            # Set the temporary partner_id
            vals['partner_id'] = tbd_partner.id

            # Create the order
            res = super(SaleOrder, self).create(vals)

            # Return the result
            return res

        # For all other cases, use the standard create method
        return super(SaleOrder, self).create(vals)

    @api.depends('order_line.apartment_id')
    def _compute_has_apartment(self):
        """Compute if the order contains at least one apartment"""
        for order in self:
            order.has_apartment = any(line.apartment_id for line in order.order_line)

    @api.constrains('order_line', 'is_real_estate')
    def _check_real_estate_order_lines(self):
        """Ensure real estate orders have only one apartment line"""
        for order in self:
            if order.is_real_estate:
                # Count apartment lines
                apartment_lines = order.order_line.filtered(lambda l: l.apartment_id)
                if len(apartment_lines) > 1:
                    raise ValidationError(_("Real estate orders can only have one apartment line. Please remove additional apartment lines."))

    @api.onchange('order_line', 'is_real_estate')
    def _onchange_order_line_real_estate(self):
        """Warn user when trying to add multiple lines to a real estate order"""
        if self.is_real_estate and len(self.order_line) > 1:
            # Check if more than one line has an apartment
            apartment_lines = self.order_line.filtered(lambda l: l.apartment_id)
            if len(apartment_lines) > 1:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('Real estate orders should only have one apartment line. Please remove additional apartment lines.')
                    }
                }

    @api.depends('project_id')
    def _compute_has_project(self):
        """Compute if the order has a project selected"""
        for order in self:
            order.has_project = bool(order.project_id)

    @api.depends('partner_id')
    def _compute_is_tbd_customer(self):
        """Compute if the partner is the TBD Customer"""
        for order in self:
            order.is_tbd_customer = order.partner_id and order.partner_id.name == 'TBD Customer'



    @api.onchange('project_id')
    def _onchange_project_id(self):
        """When project changes, update domain for order lines"""
        if self.project_id:
            # When project changes, we need to clear any buildings/apartments that don't belong to this project
            for line in self.order_line:
                if line.building_id and line.building_id.project_id.id != self.project_id.id:
                    line.building_id = False
                    line.apartment_id = False
                    line.product_id = False

    @api.depends('amount_total')
    def _compute_deposit_amount(self):
        """Compute the deposit amount (10% of total)"""
        for order in self:
            order.deposit_amount = order.amount_total * 0.1

    def action_create_deposit_invoice(self):
        """Create a deposit invoice for 10% of the total amount"""
        self.ensure_one()

        # Check if we're in the right state
        if self.state != 'reservation':
            # If we're in draft state, suggest creating a reservation first
            if self.state == 'draft' and self.has_apartment:
                # Ask the user if they want to create a reservation first
                return {
                    'name': _('Create Reservation First'),
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Reservation Required'),
                        'message': _('Please create a reservation first using the "Create Reservation" button.'),
                        'sticky': True,
                        'type': 'warning',
                        'next': {
                            'type': 'ir.actions.act_window',
                            'res_model': 'sale.order',
                            'res_id': self.id,
                            'view_mode': 'form',
                            'target': 'current',
                        }
                    }
                }
            else:
                raise UserError(_("Can only create deposit invoice when order is in 'Reservation' state."))

        # Check if a deposit invoice already exists
        if self.is_deposit_invoiced:
            # If it exists but is not paid, show it with a helpful message
            if self.deposit_invoice_state != 'paid':
                return {
                    'name': _('Deposit Invoice'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'view_mode': 'form',
                    'res_id': self.deposit_invoice_id.id,
                    'target': 'current',
                    'context': {
                        'form_view_initial_mode': 'edit',
                        'default_narration': _("""This is the deposit invoice (10%%) for the reservation.
Please register the payment when received to proceed with the order confirmation.""")
                    },
                    'flags': {
                        'mode': 'edit',
                        'warning': _('Please register payment for this invoice to proceed.')
                    }
                }
            else:
                # If it's paid, suggest confirming the order
                return {
                    'name': _('Deposit Invoice Paid'),
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Deposit Invoice Already Paid'),
                        'message': _('The deposit invoice has already been paid. You can now confirm the order.'),
                        'sticky': True,
                        'type': 'success',
                        'next': {
                            'type': 'ir.actions.act_window',
                            'res_model': 'sale.order',
                            'res_id': self.id,
                            'view_mode': 'form',
                            'target': 'current',
                        }
                    }
                }

        # Create a deposit invoice (10%)
        invoice_vals = self._prepare_deposit_invoice_vals()
        invoice = self.env['account.move'].create(invoice_vals)

        # Link the invoice to the order
        self.deposit_invoice_id = invoice.id
        self.is_deposit_invoiced = True

        # Log the creation
        _logger.info("Created deposit invoice %s for reservation %s", invoice.name, self.name)

        # Return an action to view the invoice with a helpful message
        return {
            'name': _('Deposit Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_narration': _("""This is the deposit invoice (10%%) for the reservation.
Please register the payment when received to proceed with the order confirmation.""")
            },
            'flags': {
                'mode': 'edit',
                'warning': _('Please register payment for this invoice to proceed.')
            }
        }

    def _prepare_deposit_invoice_vals(self):
        """Prepare values for the deposit invoice (10% of total)"""
        self.ensure_one()

        # Get the journal
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not journal:
            raise UserError(_("No sale journal found for the company %s") % self.company_id.name)

        # Prepare invoice lines
        invoice_line_vals = []
        for line in self.order_line:
            # Only include apartment lines
            if line.apartment_id:
                # Calculate the deposit amount for this line (10% of the price)
                deposit_price_unit = line.price_unit * 0.1

                # Get apartment details for better description
                apartment = line.apartment_id
                building = apartment.building_id
                project = apartment.project_id

                # Create a descriptive name
                description = _("""Deposit (10%%) for:
Project: %(project)s
Building: %(building)s
Apartment: %(apartment)s
Price: %(currency)s %(price).2f
""") % {
                    'apartment': apartment.name,
                    'project': project.name if project else _('N/A'),
                    'building': building.name if building else _('N/A'),
                    'price': line.price_total,
                    'currency': self.currency_id.symbol or '',
                }

                # Prepare the invoice line
                invoice_line_vals.append((0, 0, {
                    'name': description,
                    'product_id': line.product_id.id,
                    'price_unit': deposit_price_unit,
                    'quantity': 1.0,
                    'tax_ids': [(6, 0, line.tax_id.ids)],
                }))

        # Prepare the invoice values
        return {
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'move_type': 'out_invoice',
            'journal_id': journal.id,
            'invoice_line_ids': invoice_line_vals,
            'invoice_date': fields.Date.today(),
            'narration': _('Deposit Invoice (10%%) for Reservation %s') % self.name,
            'payment_reference': _('Deposit for %s') % self.name,
        }

    def action_confirm_reservation(self):
        """Confirm the quotation to create a reservation"""
        self.ensure_one()

        # Check if we're in the right state
        if self.state not in ['draft', 'sent']:
            raise UserError(_("Can only create a reservation from draft or sent state."))

        # Check if we have apartment lines
        if not self.has_apartment:
            raise UserError(_("Cannot create a reservation without apartments."))

        # Check if all apartments are disponible
        unavailable_apartments = self.order_line.filtered(
            lambda l: l.apartment_id and l.apartment_id.state != 'disponible'
        )
        if unavailable_apartments:
            apartment_names = ', '.join(unavailable_apartments.mapped('apartment_id.name'))
            raise UserError(_("The following apartments are not disponible: %s") % apartment_names)

        # Confirm the order using standard Odoo method (call super directly to avoid recursion)
        super(SaleOrder, self).action_confirm()

        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reservation Created'),
                'message': _('The quotation has been confirmed and the apartment is now prereserved.'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'sale.order',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                },
            }
        }

    def action_confirm(self):
        """Override confirm to handle apartment and store state"""
        # Check if all order lines have a name set
        for line in self.order_line:
            if not line.name and line.product_id:
                # Generate a description for the line
                if line.product_id.product_tmpl_id.is_apartment and line.apartment_id:
                    line._generate_apartment_description()
                else:
                    line.name = line.product_id.name

        # Check if this is a real estate order with a TBD customer
        if self.is_real_estate and self.is_tbd_customer:
            # Show an error message
            raise UserError(_("Veuillez sélectionner un vrai client avant de confirmer la commande."))

        # Check if partner_id is set
        if not self.partner_id:
            # Show an error message
            raise UserError(_("Veuillez sélectionner un client avant de confirmer la commande."))

        # Call super to confirm the order
        res = super(SaleOrder, self).action_confirm()

        # For real estate orders with apartments or stores
        if self.is_real_estate:
            # Create a delivery order
            self._create_delivery_picking()

            # Update apartment states when order is confirmed
            for line in self.order_line:
                # Handle apartments
                if line.apartment_id:
                    # When confirming the order, set the apartment to 'sold'
                    if line.apartment_id.state != 'sold':
                        # Mark apartment as sold
                        line.apartment_id.with_context(from_sale_order=True).write({
                            'state': 'sold',
                            'is_locked': False,  # Remove the lock since it's now sold
                            'locked_by_order_id': False,
                            'lock_date': False
                        })

                        # Update the product state with context to prevent infinite recursion
                        if line.product_id and line.product_id.product_tmpl_id.is_apartment:
                            line.product_id.product_tmpl_id.with_context(from_apartment_update=True).apartment_state = 'sold'

                            # Quantity management is now handled by Odoo's standard inventory management

                        # Log the state change
                        _logger.info("Apartment %s state changed to sold when order %s was confirmed",
                                    line.apartment_id.name, self.name)

                # Handle stores
                elif line.product_id and line.product_id.product_tmpl_id.is_store:
                    store_product = line.product_id.product_tmpl_id

                    # When confirming the order, set the store to 'sold'
                    if store_product.apartment_state != 'sold':
                        # Mark store as sold
                        store_product.with_context(from_sale_order=True).write({
                            'apartment_state': 'sold',
                            'is_locked': False,  # Remove the lock since it's now sold
                            'locked_by_order_id': False,
                        })

                        # Quantity management is now handled by Odoo's standard inventory management

                        # Log the state change
                        _logger.info("Store %s state changed to sold when order %s was confirmed",
                                    store_product.name, self.name)

                # Handle équipements
                elif line.product_id and line.product_id.product_tmpl_id.is_equipement:
                    equipement_product = line.product_id.product_tmpl_id

                    # When confirming the order, set the équipement to 'sold'
                    if equipement_product.apartment_state != 'sold':
                        # Mark équipement as sold
                        equipement_product.with_context(from_sale_order=True).write({
                            'apartment_state': 'sold',
                            'is_locked': False,  # Remove the lock since it's now sold
                            'locked_by_order_id': False,
                        })

                        # Quantity management is now handled by Odoo's standard inventory management

                        # Log the state change
                        _logger.info("Équipement %s state changed to sold when order %s was confirmed",
                                    equipement_product.name, self.name)

            # Log the confirmation
            apartment_count = len(self.order_line.filtered(lambda l: l.apartment_id))
            store_count = len(self.order_line.filtered(lambda l: l.product_id and l.product_id.product_tmpl_id.is_store))
            equipement_count = len(self.order_line.filtered(lambda l: l.product_id and l.product_id.product_tmpl_id.is_equipement))

            _logger.info("Real estate order %s confirmed with %s apartments, %s stores, and %s équipements",
                        self.name, apartment_count, store_count, equipement_count)

            # Check if auto-created invoices are already paid (for external module integration)
            # We'll check the payment status directly, and the _invoice_paid_hook will handle it when payment is complete
            self._check_payment_status_after_confirmation()

        return res

    def _check_payment_status_after_confirmation(self):
        """Check payment status after confirmation"""
        self.ensure_one()

        # Note: With auto workflow modules, invoices are created automatically
        # and properties are marked as sold during invoice creation (in account_move.py)
        # This method is kept for backward compatibility but the main logic 
        # has been moved to account_move.action_post()
        
        _logger.info("Checking payment status for order %s after confirmation (auto workflow mode)", self.name)
        
        # Just log that the order was confirmed successfully
        # Properties will be marked as sold when the invoice is created
        message = _("""
Order Confirmed

Order %s has been confirmed successfully.
Properties will be marked as 'Sold' when the invoice is created by the auto workflow.
""") % self.name

        self.message_post(
            body=message,
            message_type='notification',
            subtype_id=self.env.ref('mail.mt_note').id,
        )

    def _create_invoices(self, grouped=False, final=False, date=None):
        """Override to handle apartment state when invoice is created"""
        # For real estate orders with apartments
        if self.is_real_estate and self.has_apartment:
            # Case 1: Creating final invoice after handover
            if self.state == 'sale' and self.is_deposit_invoiced and self.handover_picking_id:
                # Check if the handover picking is done
                if self.handover_picking_id.state == 'done':
                    # Create the final invoice (90%)
                    invoices = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final, date=date)

                    # Adjust the invoice amounts to account for the deposit (10%)
                    for invoice in invoices:
                        # Mark as final invoice
                        invoice.narration = _('Final Invoice (90%) for Order %s') % self.name

                        for line in invoice.invoice_line_ids:
                            # Reduce the price by 10% to account for the deposit
                            line.price_unit = line.price_unit * 0.9
                            line.name = _('Final Payment (90%%): %s') % line.name

                    # Log the creation
                    _logger.info("Created final invoices %s for order %s", invoices.mapped('name'), self.name)

                    return invoices
                else:
                    raise UserError(_("Cannot create final invoice until the handover is completed. Please validate the delivery order first."))

            # Case 2: Creating deposit invoice
            elif self.state == 'reservation' and not self.is_deposit_invoiced:
                # This should be handled by action_create_deposit_invoice
                raise UserError(_("Please use the 'Create Deposit Invoice' button to create a deposit invoice."))

        # Default case: normal invoice creation
        invoices = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final, date=date)

        # Log invoice creation
        _logger.info("Created invoices %s for sale order %s", invoices.mapped('name'), self.name)

        return invoices

    def _create_delivery_picking(self):
        """Create a delivery order for the apartment/store/équipement"""
        self.ensure_one()

        # Only create delivery picking for confirmed orders with apartments or stores
        if self.state != 'sale':
            return False

        # Check if we have any real estate products (apartments, stores, or équipements)
        has_real_estate_products = any(line.apartment_id or (line.product_id and (line.product_id.product_tmpl_id.is_apartment or line.product_id.product_tmpl_id.is_store or line.product_id.product_tmpl_id.is_equipement)) for line in self.order_line)

        if not has_real_estate_products:
            return False

        # Check if we already have a delivery picking
        if self.delivery_picking_id:
            return self.delivery_picking_id

        # Get the stock.picking model
        StockPicking = self.env['stock.picking']

        # Get the company warehouse
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            _logger.warning("No warehouse found for company %s", self.company_id.name)
            return False

        # Get the stock location and customer location
        location_id = warehouse.lot_stock_id.id
        location_dest_id = self.env.ref('stock.stock_location_customers').id

        # Prepare picking values with better description
        picking_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'picking_type_id': warehouse.out_type_id.id,
            'location_id': location_id,
            'location_dest_id': location_dest_id,
            'scheduled_date': self.date_order,
            'move_type': 'direct',
            'note': _("""Handover for real estate properties in order %s
This delivery represents the handover of keys and documents for the properties.
When validated, the property status will change to 'Sold' and the final invoice will be created.
""") % self.name,
        }

        # Create the picking
        picking = StockPicking.create(picking_vals)

        # Create stock moves for each property with better descriptions
        for line in self.order_line:
            # Handle apartments
            if line.apartment_id and line.product_id:
                # Get apartment details for better description
                apartment = line.apartment_id
                building = apartment.building_id
                project = apartment.project_id

                # Create a descriptive name
                description = _("""Handover of keys and documents for:
Project: %(project)s
Building: %(building)s
Apartment: %(apartment)s
Floor: %(floor)s
""") % {
                    'apartment': apartment.name,
                    'project': project.name if project else _('N/A'),
                    'building': building.name if building else _('N/A'),
                    'floor': apartment.floor,
                }

                # Create a stock move for the apartment
                move = self.env['stock.move'].create({
                    'name': description,
                    'product_id': line.product_id.id,
                    'product_uom_qty': 1.0,  # Apartments always use quantity 1
                    'product_uom': line.product_uom.id,
                    'picking_id': picking.id,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'state': 'draft',
                    'sale_line_id': line.id,
                })

                # Confirm the move to create move lines and reserve quantity
                move._action_confirm()

                # Create move lines with quantity done = 1.0 to allow direct validation
                if not move.move_line_ids:
                    move._action_assign()
                    for move_line in move.move_line_ids:
                        move_line.qty_done = 1.0

            # Handle stores
            elif line.product_id and line.product_id.product_tmpl_id.is_store:
                # Get store details for better description
                store_product = line.product_id.product_tmpl_id
                building = store_product.building_id
                project = store_product.project_id

                # Create a descriptive name
                description = _("""Handover of keys and documents for:
Project: %(project)s
Building: %(building)s
Store: %(store)s
""") % {
                    'store': store_product.name,
                    'project': project.name if project else _('N/A'),
                    'building': building.name if building else _('N/A'),
                }

                # Create a stock move for the store
                move = self.env['stock.move'].create({
                    'name': description,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,  # Use sale line quantity (surface area for stores)
                    'product_uom': line.product_uom.id,
                    'picking_id': picking.id,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'state': 'draft',
                    'sale_line_id': line.id,
                })

                # Confirm the move to create move lines and reserve quantity
                move._action_confirm()

                # Create move lines with quantity done = surface area to allow direct validation
                if not move.move_line_ids:
                    move._action_assign()
                    for move_line in move.move_line_ids:
                        move_line.qty_done = line.product_uom_qty

            # Handle équipements
            elif line.product_id and line.product_id.product_tmpl_id.is_equipement:
                # Get équipement details for better description
                equipement_product = line.product_id.product_tmpl_id
                building = equipement_product.building_id
                project = equipement_product.project_id

                # Create a descriptive name
                description = _("""Handover of keys and documents for:
Project: %(project)s
Building: %(building)s
Équipement: %(equipement)s
""") % {
                    'equipement': equipement_product.name,
                    'project': project.name if project else _('N/A'),
                    'building': building.name if building else _('N/A'),
                }

                # Create a stock move for the équipement
                move = self.env['stock.move'].create({
                    'name': description,
                    'product_id': line.product_id.id,
                    'product_uom_qty': 1.0,  # Équipements always use quantity 1
                    'product_uom': line.product_uom.id,
                    'picking_id': picking.id,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'state': 'draft',
                    'sale_line_id': line.id,
                })

                # Confirm the move to create move lines and reserve quantity
                move._action_confirm()

                # Create move lines with quantity done = 1.0 to allow direct validation
                if not move.move_line_ids:
                    move._action_assign()
                    for move_line in move.move_line_ids:
                        move_line.qty_done = 1.0

        # Link the picking to the order
        self.delivery_picking_id = picking.id

        # Log the creation
        _logger.info("Created delivery picking %s for order %s", picking.name, self.name)

        return picking

    def action_view_deposit_invoice(self):
        """View the deposit invoice"""
        self.ensure_one()

        # Check if we have a deposit invoice
        if not self.deposit_invoice_id:
            # If no deposit invoice exists but we're in reservation state, create one
            if self.state == 'reservation':
                return self.action_create_deposit_invoice()
            else:
                raise UserError(_("No deposit invoice exists for this order."))

        # Return an action to view the invoice
        return {
            'name': _('Deposit Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.deposit_invoice_id.id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_view_delivery(self):
        """View the delivery order for the apartment"""
        self.ensure_one()

        # Check if we're in the right state
        if self.state != 'sale':
            raise UserError(_("Delivery is only available for confirmed orders."))

        # Check if we have apartments
        if not self.has_apartment:
            raise UserError(_("Cannot create delivery without apartments."))

        # Create the delivery picking if it doesn't exist
        if not self.delivery_picking_id:
            picking = self._create_delivery_picking()
            if not picking:
                raise UserError(_("Failed to create delivery order. Please check the logs."))

        # Show a helpful message if this is the first time viewing the delivery
        if self.delivery_picking_id and self.delivery_picking_id.state == 'draft':
            # Get the message
            message = _("""
Delivery Order Created

This delivery order represents the delivery of the apartment(s).
When you validate this delivery:
1. The apartment status will change to 'Sold'
2. You can then create an invoice

Please review and validate the delivery when complete.
""")

            # Show the message
            return {
                'name': _('Delivery'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': self.delivery_picking_id.id,
                'target': 'current',
                'context': {'default_note': message},
            }

        # Return an action to view the picking
        return {
            'name': _('Delivery'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.delivery_picking_id.id,
            'target': 'current',
        }

    # Removed action_validate_handover method to simplify the workflow

    def write(self, vals):
        """Override write to handle apartment status updates"""
        # Call super to perform the actual write
        res = super(SaleOrder, self).write(vals)
        return res

    def _check_all_invoices_paid(self):
        """Check if all invoices for this sale order are fully paid"""
        self.ensure_one()

        # Get all invoices related to this sale order
        invoices = self.env['account.move'].search([
            ('invoice_origin', '=', self.name),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted')
        ])

        if not invoices:
            return False

        # Check if all invoices are paid
        all_paid = all(invoice.payment_state == 'paid' for invoice in invoices)

        _logger.info("Order %s: Checked %s invoices, all paid: %s",
                    self.name, len(invoices), all_paid)

        return all_paid

    def action_cancel(self):
        """Override cancel to handle apartment/store/équipement state and locking"""
        res = super(SaleOrder, self).action_cancel()

        # Update apartment/store/équipement states when order is cancelled
        for line in self.order_line:
            # Handle apartments
            if line.apartment_id:
                # If the apartment is locked by this order, unlock it
                if line.apartment_id.is_locked and line.apartment_id.locked_by_order_id.id == self.id:
                    line.apartment_id.write({
                        'is_locked': False,
                        'locked_by_order_id': False,
                        'lock_date': False
                    })
                    _logger.info("Apartment %s unlocked when order %s was cancelled",
                                line.apartment_id.name, self.name)

                # If the apartment is prereserved by this order, make it disponible again
                # Only do this for prereserved apartments, not sold ones
                if line.apartment_id.state == 'prereserved':
                    # Check if this is the only active order for this apartment
                    other_orders = self.env['sale.order.line'].search([
                        ('apartment_id', '=', line.apartment_id.id),
                        ('order_id', '!=', self.id),
                        ('order_id.state', 'in', ['sale', 'done'])
                    ])

                    if not other_orders:
                        # Mark apartment as disponible when order is cancelled
                        line.apartment_id.with_context(from_sale_order=True).state = 'disponible'
                        # Update the product state with context to prevent infinite recursion
                        if line.product_id and line.product_id.product_tmpl_id.is_apartment:
                            line.product_id.product_tmpl_id.with_context(from_apartment_update=True).apartment_state = 'disponible'

                        _logger.info("Apartment %s state changed to disponible when order %s was cancelled",
                                    line.apartment_id.name, self.name)

            # Handle stores
            elif line.product_id and line.product_id.product_tmpl_id.is_store:
                store_product = line.product_id.product_tmpl_id

                # If the store is locked by this order, unlock it
                if store_product.is_locked and store_product.locked_by_order_id.id == self.id:
                    store_product.with_context(from_sale_order=True).write({
                        'is_locked': False,
                        'locked_by_order_id': False,
                    })
                    _logger.info("Store %s unlocked when order %s was cancelled",
                                store_product.name, self.name)

                # If the store is prereserved, make it disponible again
                # Only do this for prereserved stores, not sold ones
                if store_product.apartment_state == 'prereserved':
                    # Check if this is the only active order for this store
                    other_orders = self.env['sale.order.line'].search([
                        ('product_id.product_tmpl_id', '=', store_product.id),
                        ('order_id', '!=', self.id),
                        ('order_id.state', 'in', ['sale', 'done'])
                    ])

                    if not other_orders:
                        # Mark store as disponible when order is cancelled
                        store_product.with_context(from_sale_order=True).apartment_state = 'disponible'
                        # Quantity management is now handled by Odoo's standard inventory management

                        _logger.info("Store %s state changed to disponible when order %s was cancelled",
                                    store_product.name, self.name)

            # Handle équipements
            elif line.product_id and line.product_id.product_tmpl_id.is_equipement:
                equipement_product = line.product_id.product_tmpl_id

                # If the équipement is locked by this order, unlock it
                if equipement_product.is_locked and equipement_product.locked_by_order_id.id == self.id:
                    equipement_product.with_context(from_sale_order=True).write({
                        'is_locked': False,
                        'locked_by_order_id': False,
                    })
                    _logger.info("Équipement %s unlocked when order %s was cancelled",
                                equipement_product.name, self.name)

                # If the équipement is prereserved, make it disponible again
                # Only do this for prereserved équipements, not sold ones
                if equipement_product.apartment_state == 'prereserved':
                    # Check if this is the only active order for this équipement
                    other_orders = self.env['sale.order.line'].search([
                        ('product_id.product_tmpl_id', '=', equipement_product.id),
                        ('order_id', '!=', self.id),
                        ('order_id.state', 'in', ['sale', 'done'])
                    ])

                    if not other_orders:
                        # Mark équipement as disponible when order is cancelled
                        equipement_product.with_context(from_sale_order=True).apartment_state = 'disponible'
                        # Quantity management is now handled by Odoo's standard inventory management

                        _logger.info("Équipement %s state changed to disponible when order %s was cancelled",
                                    equipement_product.name, self.name)

        return res
