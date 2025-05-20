from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import time

_logger = logging.getLogger(__name__)


class RealEstateApartment(models.Model):
    _name = 'real.estate.apartment'
    _description = 'Real Estate Apartment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    @api.model
    def default_get(self, fields_list):
        """Override default_get to set readonly flags based on context"""
        res = super(RealEstateApartment, self).default_get(fields_list)

        # Check if we're creating from building
        if self.env.context.get('default_building_id'):
            res['context_building_readonly'] = True
            # Ensure the building_id is set from context
            res['building_id'] = self.env.context.get('default_building_id')

            # Get the project_id from the building
            building = self.env['real.estate.building'].browse(res['building_id'])
            if building and building.project_id:
                res['context_project_readonly'] = True
                # No need to set project_id as it's a related field
                _logger.info("Creating apartment from building: building_id=%s, project_id=%s",
                            res['building_id'], building.project_id.id)

        # Check if we're creating from project
        elif self.env.context.get('default_project_id'):
            res['context_project_readonly'] = True
            _logger.info("Creating apartment with project context: project_id=%s",
                        self.env.context.get('default_project_id'))

        return res

    name = fields.Char(string='Apartment Number', required=True, tracking=True)
    code = fields.Char(string='Apartment Code', required=True, tracking=True)

    building_id = fields.Many2one('real.estate.building', string='Building',
                                 required=True, tracking=True,
                                 ondelete='cascade')
    project_id = fields.Many2one(related='building_id.project_id',
                                string='Project', store=True, readonly=True)

    floor = fields.Integer(string='Floor', required=True, tracking=True)

    state = fields.Selection([
        ('available', 'Available'),
        ('in_progress', 'Réservation en cours'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
    ], string='Status', default='available', required=True, tracking=True)

    # Fields for locking mechanism
    is_locked = fields.Boolean(string='Locked', default=False,
                              help="Indicates if the apartment is locked for a quotation")
    locked_by_order_id = fields.Many2one('sale.order', string='Locked By Order',
                                       help="The quotation that has locked this apartment")
    lock_date = fields.Datetime(string='Lock Date',
                              help="Date and time when the apartment was locked")

    price = fields.Float(string='Price', required=True, tracking=True)
    area = fields.Float(string='Area (m²)', required=True)
    rooms = fields.Integer(string='Number of Rooms', default=1)
    bathrooms = fields.Integer(string='Number of Bathrooms', default=1)

    description = fields.Text(string='Description')
    features = fields.Text(string='Features')

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company)

    # Context fields for form behavior
    context_project_readonly = fields.Boolean(string='Project Readonly', default=False,
                                            help="Technical field to make project field readonly based on context")
    context_building_readonly = fields.Boolean(string='Building Readonly', default=False,
                                             help="Technical field to make building field readonly based on context")

    # Product relationship
    product_tmpl_ids = fields.One2many('product.template', 'apartment_id',
                                     string='Product Templates')
    product_count = fields.Integer(compute='_compute_product_count',
                                  string='Product Count')

    sale_order_line_ids = fields.One2many('sale.order.line', 'apartment_id',
                                     string='Sale Order Lines')
    reservation_count = fields.Integer(compute='_compute_reservation_count',
                               string='Reservation Count')

    @api.depends('product_tmpl_ids')
    def _compute_product_count(self):
        for apartment in self:
            apartment.product_count = len(apartment.product_tmpl_ids)

    @api.onchange('floor', 'building_id')
    def _onchange_floor_building(self):
        """When floor or building changes, update apartment number"""
        if self.building_id and not self.env.context.get('skip_apartment_number_generation'):
            try:
                # Only generate a name if the user hasn't entered one or if it's a default name
                default_names = ['New Apartment', 'New', '']
                if not self.name or self.name in default_names:
                    # Count existing apartments on this floor in this building
                    floor = self.floor or 0
                    existing_count = self.env['real.estate.apartment'].search_count([
                        ('building_id', '=', self.building_id.id),
                        ('floor', '=', floor)
                    ])

                    # Generate apartment number (e.g., A101 for building A, floor 1, apt 01)
                    building_prefix = self.building_id.code[0].upper() if self.building_id.code else 'A'
                    apt_number = f"{building_prefix}{floor:02d}{existing_count+1:02d}"

                    # Set the name to "Apartment" followed by the number only if user hasn't entered a custom name
                    self.name = f"Apartment {apt_number}"
                    # Also set the code (just the number)
                    self.code = apt_number

                    _logger.info("Generated apartment name %s for building %s on floor %s",
                                apt_number, self.building_id.name, floor)
                else:
                    _logger.info("Keeping user-entered apartment name: %s", self.name)

                    # If we have a name but no code, generate a code based on the name
                    if not self.code:
                        self.code = f"APT-{int(time.time()) % 10000}"
            except Exception as e:
                _logger.error("Error generating apartment number: %s", str(e))

    @api.depends('sale_order_line_ids')
    def _compute_reservation_count(self):
        for apartment in self:
            apartment.reservation_count = len(apartment.sale_order_line_ids)

    def action_view_products(self):
        """View products related to this apartment"""
        self.ensure_one()
        # Create product if it doesn't exist
        if not self.product_tmpl_ids:
            try:
                self._create_product(self)
            except Exception as e:
                _logger.error("Error creating product for apartment %s: %s", self.name, str(e))

        # Use a simpler approach to avoid potential reference errors
        return {
            'name': _('Apartment Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'kanban,tree,form',
            'domain': [('apartment_id', '=', self.id)],
            'context': {'default_apartment_id': self.id, 'default_is_apartment': True},
            'target': 'current',
        }

    def action_view_reservations(self):
        """View reservations for this apartment"""
        self.ensure_one()
        return {
            'name': _('Reservations'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('has_apartment', '=', True), ('order_line.product_id.product_tmpl_id.apartment_id', '=', self.id)],
            'context': {'create': False},
            'target': 'current',
        }

    def action_create_reservation(self):
        """Create a new reservation (quotation) for this apartment"""
        self.ensure_one()

        # Check if apartment is available
        if self.state != 'available':
            raise UserError(_("Only available apartments can be reserved."))

        # Find the product linked to this apartment
        product = self.env['product.template'].search([
            ('apartment_id', '=', self.id),
            ('is_apartment', '=', True)
        ], limit=1)

        if not product or not product.product_variant_id:
            raise UserError(_("No product found for this apartment. Please make sure the apartment is properly linked to a product."))

        # Create a new quotation with this apartment
        SaleOrder = self.env['sale.order']

        # Generate a detailed description for the apartment
        project_name = self.project_id.name if self.project_id else "N/A"
        building_name = self.building_id.name if self.building_id else "N/A"
        floor = self.floor if self.floor is not None else "N/A"
        area = self.area if self.area else "N/A"
        rooms = self.rooms if self.rooms else "N/A"
        bathrooms = self.bathrooms if self.bathrooms else "N/A"

        apartment_description = f"""
Projet: {project_name}
Bâtiment: {building_name}
Appartement: {self.name}
Étage: {floor}
Surface: {area} m²
Pièces: {rooms}
Salles de bain: {bathrooms}
"""

        # Prepare the order values - without partner_id
        order_vals = {
            'is_real_estate': True,
            'project_id': self.project_id.id if self.project_id else False,
            'order_line': [(0, 0, {
                'product_id': product.product_variant_id.id,
                'apartment_id': self.id,
                'building_id': self.building_id.id if self.building_id else False,
                'product_uom_qty': 1,
                'price_unit': product.list_price or self.price or 0.0,
                'name': apartment_description,
            })],
            'state': 'draft',  # Ensure it's a draft
        }

        # Create the quotation
        new_order = SaleOrder.create(order_vals)

        # Log the creation
        _logger.info("Created new reservation %s for apartment %s", new_order.name, self.name)

        # Return an action to open the new quotation
        return {
            'name': _('New Reservation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': new_order.id,
            'view_mode': 'form',
            'views': [(False, 'form')],  # This is the correct format for views
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    # Quantity management is now handled by Odoo's standard inventory management

    def action_mark_as_reserved(self):
        for record in self:
            if record.state == 'available':
                record.state = 'reserved'
                # Update product state
                self._update_product_state(record)
            else:
                raise UserError(_("Only available apartments can be reserved."))

    def action_mark_as_sold(self):
        for record in self:
            if record.state in ['available', 'reserved']:
                record.state = 'sold'
                # Update product state
                self._update_product_state(record)
            else:
                raise UserError(_("This apartment is already sold."))

    def action_mark_as_available(self):
        for record in self:
            if record.state == 'reserved':
                # Check if there are active sales
                active_sales = self.env['sale.order.line'].search_count([
                    ('apartment_id', '=', record.id),
                    ('order_id.state', 'not in', ['cancel', 'done'])
                ])
                if active_sales > 0:
                    raise UserError(_("Cannot mark as available. There are active reservations for this apartment."))
                record.state = 'available'
                # Update product state - this will also update the quantity
                self._update_product_state(record)
                _logger.info("Updated product state and quantity for apartment %s marked as available", record.name)
            elif record.state == 'sold':
                # Check if there are confirmed sales
                confirmed_sales = self.env['sale.order.line'].search_count([
                    ('apartment_id', '=', record.id),
                    ('order_id.state', '=', 'sale')
                ])
                if confirmed_sales > 0:
                    raise UserError(_("Cannot mark as available. This apartment has been sold."))
                record.state = 'available'
                # Update product state - this will also update the quantity
                self._update_product_state(record)
                _logger.info("Updated product state and quantity for apartment %s marked as available", record.name)
            else:
                raise UserError(_("This apartment is already available."))

    @api.model
    def create(self, vals):
        """Override create to create corresponding product"""
        # Ensure building_id is set
        if not vals.get('building_id'):
            raise ValidationError(_("Building is required for creating an apartment."))

        # Get building for logging
        building = self.env['real.estate.building'].browse(vals.get('building_id'))
        _logger.info("Creating apartment in building %s (project %s)",
                    building.name, building.project_id.name if building.project_id else "None")

        # Create the apartment
        res = super(RealEstateApartment, self).create(vals)

        # Only create a product if we're not being called from product creation
        # This prevents the circular reference that causes duplicates
        if not self.env.context.get('from_product_create'):
            # Check if a product already exists for this apartment
            existing_product = self.env['product.template'].search([
                ('apartment_id', '=', res.id)
            ], limit=1)

            if not existing_product:
                try:
                    self._create_product(res)
                except Exception as e:
                    # Log the error but don't stop the creation process
                    _logger.error("Error creating product for apartment %s: %s", res.name, str(e))
            else:
                _logger.info("Product already exists for apartment %s: %s",
                            res.name, existing_product.name)

        # Force update of apartment counts
        if res.building_id:
            self.env['real.estate.building'].invalidate_cache(['apartment_count'])
            if res.building_id.project_id:
                self.env['real.estate.project'].invalidate_cache(['apartment_count'])

        return res

    def write(self, vals):
        """Override write to update corresponding product"""
        # Check if we're being called from product update to avoid infinite recursion
        if self.env.context.get('from_product_update'):
            return super(RealEstateApartment, self).write(vals)

        # Store old building_id for each record to check if it changed
        old_building_ids = {rec.id: rec.building_id.id for rec in self}

        res = super(RealEstateApartment, self).write(vals)

        # Update product if certain fields changed
        if any(field in vals for field in ['name', 'price', 'state', 'floor', 'area', 'rooms', 'bathrooms', 'building_id']):
            try:
                self._update_product()
            except Exception as e:
                # Log the error but don't stop the update process
                _logger.error("Error updating product for apartment(s) %s: %s", self.mapped('name'), str(e))

        # Force update of apartment counts if building_id changed
        if 'building_id' in vals:
            # Update counts for old buildings
            buildings_to_update = set()
            projects_to_update = set()

            # Add old buildings to update
            for rec_id, old_building_id in old_building_ids.items():
                if old_building_id:
                    old_building = self.env['real.estate.building'].browse(old_building_id)
                    buildings_to_update.add(old_building_id)
                    if old_building.project_id:
                        projects_to_update.add(old_building.project_id.id)

            # Add new buildings to update
            for rec in self:
                if rec.building_id:
                    buildings_to_update.add(rec.building_id.id)
                    if rec.building_id.project_id:
                        projects_to_update.add(rec.building_id.project_id.id)

            # Invalidate cache for all affected buildings and projects
            if buildings_to_update:
                self.env['real.estate.building'].browse(list(buildings_to_update)).invalidate_cache(['apartment_count'])
            if projects_to_update:
                self.env['real.estate.project'].browse(list(projects_to_update)).invalidate_cache(['apartment_count'])

        return res

    def _create_product(self, apartment):
        """Create a product for the apartment"""
        # Verify building and project
        if not apartment.building_id:
            raise ValidationError(_("Building is required for creating an apartment product."))

        # Log for debugging
        _logger.info("Creating product for apartment %s in building %s (project %s)",
                    apartment.name, apartment.building_id.name,
                    apartment.project_id.name if apartment.project_id else "None")

        # Get project and building categories
        project_categ = self._get_or_create_project_category(apartment.project_id)
        building_categ = self._get_or_create_building_category(apartment.building_id, project_categ)

        # Check if product already exists - check by apartment_id and also by building_id + code
        existing_product = self.env['product.template'].search([
            '|',
            ('apartment_id', '=', apartment.id),
            '&',
            ('building_id', '=', apartment.building_id.id),
            ('default_code', '=', apartment.code)
        ], limit=1)

        if existing_product:
            # If we found a product but it's not linked to this apartment, link it
            if existing_product.apartment_id.id != apartment.id:
                existing_product.with_context(from_apartment_update=True).write({
                    'apartment_id': apartment.id
                })
                _logger.info("Linked existing product %s to apartment %s",
                            existing_product.name, apartment.name)
            else:
                _logger.info("Product already exists for apartment %s: %s",
                            apartment.name, existing_product.name)
            return existing_product

        # Use the apartment name as is - respect user-entered names
        apt_name = apartment.name
        _logger.info("Using apartment name %s in _create_product", apt_name)

        # Create product
        product_vals = {
            'name': apt_name,  # CRITICAL FIX: Use the corrected name
            'type': 'product',
            'is_apartment': True,
            'apartment_id': apartment.id,
            'list_price': apartment.price,
            'categ_id': building_categ.id,
            'default_code': apartment.code,
            'description': apartment.description,
            'floor': apartment.floor,
            'area': apartment.area,
            'rooms': apartment.rooms,
            'bathrooms': apartment.bathrooms,
            'building_id': apartment.building_id.id,
            'project_id': apartment.project_id.id,
            'apartment_state': apartment.state,
        }

        # Create product with context to prevent recursion
        product = self.env['product.template'].with_context(from_apartment_create=True).create(product_vals)
        _logger.info("Created product %s for apartment %s", product.name, apartment.name)

        # Set the apartment state
        if apartment.state == 'available':
            product.with_context(from_apartment_update=True).write({
                'apartment_state': 'available'
            })
            _logger.info("Set apartment state to 'available' for %s", apartment.name)
        else:
            _logger.info("Apartment %s has state %s", apartment.name, apartment.state)

        # Invalidate cache to ensure counts are updated
        self.env['real.estate.building'].invalidate_cache(['apartment_count'])
        self.env['real.estate.project'].invalidate_cache(['apartment_count'])

        return product

    def _update_product(self):
        """Update product with apartment data"""
        for apartment in self:
            products = self.env['product.template'].search([('apartment_id', '=', apartment.id)])
            if products:
                for product in products:
                    # Use the apartment name as is - respect user-entered names
                    apt_name = apartment.name
                    _logger.info("Using apartment name %s in _update_product", apt_name)

                    # Use a context flag to prevent infinite recursion
                    product.with_context(from_apartment_update=True).write({
                        'name': apt_name,  # CRITICAL FIX: Use the corrected name
                        'list_price': apartment.price,
                        'default_code': apartment.code,
                        'description': apartment.description,
                        'floor': apartment.floor,
                        'area': apartment.area,
                        'rooms': apartment.rooms,
                        'bathrooms': apartment.bathrooms,
                        'building_id': apartment.building_id.id,
                        'project_id': apartment.project_id.id,
                        'apartment_state': apartment.state,
                    })
                    # Update category if needed
                    project_categ = self._get_or_create_project_category(apartment.project_id)
                    building_categ = self._get_or_create_building_category(apartment.building_id, project_categ)
                    if product.categ_id.id != building_categ.id:
                        product.with_context(from_apartment_update=True).categ_id = building_categ.id

                    # Quantity management is now handled by Odoo's standard inventory management
                    _logger.info("Updated product %s to match apartment state %s",
                                product.name, apartment.state)

    def _update_product_state(self, apartment):
        """Update product state based on apartment state"""
        products = self.env['product.template'].search([('apartment_id', '=', apartment.id)])
        if products:
            for product in products:
                # Use a context flag to prevent infinite recursion
                product_with_context = product.with_context(from_apartment_update=True)

                # Update apartment_state field and active status in a single write operation
                vals = {
                    'apartment_state': apartment.state,
                    'active': True  # Always keep products active
                }
                product_with_context.write(vals)

                # Update the stock quantity based on the new state
                try:
                    product_with_context._update_stock_quantity()
                    _logger.info("Updated product %s to match apartment state %s and updated stock quantity",
                                product.name, apartment.state)
                except Exception as e:
                    _logger.error("Error updating stock quantity for %s: %s", product.name, str(e))

    def _get_or_create_project_category(self, project):
        """Get or create product category for project"""
        category = self.env['product.category'].search([
            ('name', '=', project.name),
        ], limit=1)

        if not category:
            category = self.env['product.category'].create({
                'name': project.name,
            })

        return category

    def _get_or_create_building_category(self, building, parent_category):
        """Get or create product category for building"""
        category = self.env['product.category'].search([
            ('name', '=', building.name),
            ('parent_id', '=', parent_category.id),
        ], limit=1)

        if not category:
            category = self.env['product.category'].create({
                'name': building.name,
                'parent_id': parent_category.id,
            })

        return category

    def unlink(self):
        """Override unlink to update counts and remove products"""
        # Store building and project info before deletion
        buildings_to_update = set()
        projects_to_update = set()

        for rec in self:
            if rec.building_id:
                buildings_to_update.add(rec.building_id.id)
                if rec.building_id.project_id:
                    projects_to_update.add(rec.building_id.project_id.id)

            # Delete associated products
            products = self.env['product.template'].search([('apartment_id', '=', rec.id)])
            if products:
                _logger.info("Deleting %s products associated with apartment %s", len(products), rec.name)
                products.with_context(from_apartment_delete=True).write({'apartment_id': False, 'is_apartment': False})

        # Call super to delete the apartments
        res = super(RealEstateApartment, self).unlink()

        # Update counts after deletion
        if buildings_to_update:
            self.env['real.estate.building'].browse(list(buildings_to_update)).invalidate_cache(['apartment_count'])
        if projects_to_update:
            self.env['real.estate.project'].browse(list(projects_to_update)).invalidate_cache(['apartment_count'])

        return res

    # Quantity management is now handled by Odoo's standard inventory management