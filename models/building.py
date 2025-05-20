from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class RealEstateBuilding(models.Model):
    _name = 'real.estate.building'
    _description = 'Real Estate Building'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    @api.model
    def default_get(self, fields_list):
        """Override default_get to set readonly flags based on context"""
        res = super(RealEstateBuilding, self).default_get(fields_list)

        # Check if we're creating from project
        if self.env.context.get('default_project_id'):
            res['context_project_readonly'] = True
            # Ensure the project_id is set from context
            res['project_id'] = self.env.context.get('default_project_id')
            _logger.info("Creating building from project: project_id=%s", res['project_id'])

        # Log for debugging
        if res.get('context_project_readonly'):
            _logger.info("Setting project readonly based on context: project_readonly=%s",
                        res.get('context_project_readonly'))

        return res

    name = fields.Char(string='Building Name', required=True, tracking=True)
    code = fields.Char(string='Building Code', required=True, tracking=True)

    project_id = fields.Many2one('real.estate.project', string='Project',
                                required=True, tracking=True,
                                ondelete='cascade')

    floors = fields.Integer(string='Number of Floors', default=1, required=True)
    description = fields.Text(string='Description')

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company)

    # Context field for form behavior
    context_project_readonly = fields.Boolean(string='Project Readonly', default=False,
                                            help="Technical field to make project field readonly based on context")

    apartment_ids = fields.One2many('real.estate.apartment', 'building_id',
                                   string='Apartments')
    # Add a computed field to show apartments as products
    apartment_product_ids = fields.One2many('product.template', 'building_id',
                                         string='Apartment Products',
                                         domain=[('is_apartment', '=', True)])
    apartment_count = fields.Integer(compute='_compute_apartment_count',
                                    string='Apartment Count')

    sold_apartment_count = fields.Integer(compute='_compute_sold_available_apartment_count',
                                     string='Sold Apartments')

    available_apartment_count = fields.Integer(compute='_compute_sold_available_apartment_count',
                                     string='Available Apartments')

    reservation_count = fields.Integer(compute='_compute_reservation_count',
                                string='Reservation Count')

    # Store-related fields
    store_product_ids = fields.One2many('product.template', 'building_id',
                                     string='Store Products',
                                     domain=[('is_store', '=', True)])
    store_count = fields.Integer(compute='_compute_store_count',
                                string='Store Count')

    sold_store_count = fields.Integer(compute='_compute_sold_available_store_count',
                                string='Sold Stores')

    available_store_count = fields.Integer(compute='_compute_sold_available_store_count',
                                string='Available Stores')

    reserved_store_count = fields.Integer(compute='_compute_sold_available_store_count',
                                string='Reserved Stores')

    @api.depends('apartment_ids', 'apartment_ids.product_tmpl_ids')
    def _compute_apartment_count(self):
        for building in self:
            # Count all apartments in this building using product.template
            # This ensures consistency with the other count methods
            product_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('building_id', '=', building.id)
            ])

            # For reference, also get the direct count from apartment model
            direct_count = self.env['real.estate.apartment'].search_count([
                ('building_id', '=', building.id)
            ])

            # Log for debugging
            _logger.info("Building %s: apartment_count=%s (product_count), direct_count=%s",
                        building.name, product_count, direct_count)

            # Use the product count to be consistent with other methods
            building.apartment_count = product_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['apartment_count'], building)

    @api.depends('apartment_ids', 'apartment_product_ids')
    def _compute_sold_available_apartment_count(self):
        for building in self:
            # Count sold apartments for this building
            sold_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'sold')
            ])

            # Count available apartments for this building
            available_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'available')
            ])

            # Count reserved apartments for this building
            reserved_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'reserved')
            ])

            # Count in_progress apartments for this building
            in_progress_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'in_progress')
            ])

            # Calculate total for verification
            total_by_state = sold_count + available_count + reserved_count + in_progress_count

            # Get total count for comparison
            total_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('building_id', '=', building.id)
            ])

            # Log for debugging
            _logger.info("Building %s: sold=%s, available=%s, reserved=%s, in_progress=%s, total_by_state=%s, total_count=%s",
                        building.name, sold_count, available_count, reserved_count, in_progress_count,
                        total_by_state, total_count)

            building.sold_apartment_count = sold_count
            building.available_apartment_count = available_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['sold_apartment_count'], building)
            self.env.add_to_compute(self._fields['available_apartment_count'], building)

    @api.depends('store_product_ids')
    def _compute_store_count(self):
        for building in self:
            # Count all stores in this building
            store_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('building_id', '=', building.id)
            ])

            # Log for debugging
            _logger.info("Building %s: store_count=%s", building.name, store_count)

            building.store_count = store_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['store_count'], building)

    @api.depends('store_product_ids')
    def _compute_sold_available_store_count(self):
        for building in self:
            # Count sold stores for this building
            sold_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'sold')
            ])

            # Count available stores for this building
            available_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'available')
            ])

            # Count reserved stores for this building
            reserved_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'reserved')
            ])

            # Log for debugging
            _logger.info("Building %s: sold_store_count=%s, available_store_count=%s, reserved_store_count=%s",
                        building.name, sold_count, available_count, reserved_count)

            building.sold_store_count = sold_count
            building.available_store_count = available_count
            building.reserved_store_count = reserved_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['sold_store_count'], building)
            self.env.add_to_compute(self._fields['available_store_count'], building)
            self.env.add_to_compute(self._fields['reserved_store_count'], building)

    @api.depends('apartment_ids.state')
    def _compute_reservation_count(self):
        for building in self:
            # Count only apartments with 'reserved' state in this building
            reservation_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('building_id', '=', building.id),
                ('apartment_state', '=', 'reserved')
            ])

            # Log for debugging
            _logger.info("Building %s: reservation_count=%s", building.name, reservation_count)

            # This should be consistent with the counts in _compute_sold_available_apartment_count
            building.reservation_count = reservation_count

    def action_view_apartments(self):
        self.ensure_one()

        # Get all apartments for this building
        apartments = self.env['real.estate.apartment'].search([
            ('building_id', '=', self.id)
        ])

        # Get all apartment products for this building
        products = self.env['product.template'].search([
            ('is_apartment', '=', True),
            ('building_id', '=', self.id)
        ])

        # Log for debugging
        _logger.info("Building %s: Found %s apartments and %s products",
                    self.name, len(apartments), len(products))

        # Use the apartment actions model to get the action
        context = {
            'default_is_apartment': True,
            'default_building_id': self.id,
            'default_project_id': self.project_id.id,
            'search_default_is_apartment': 1,
            'force_building_id': self.id,  # Force the building_id to be used
            # Make project and building fields read-only
            'default_context_project_readonly': True,
            'default_context_building_readonly': True,
            'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',  # Ensure it uses the correct form view
            'from_button_box': True,  # Flag to indicate this is from button box
            # Ensure the create button is available and that new apartments have quantity 1
            'create': True,
            'default_type': 'product',  # Ensure product type is set correctly
            'default_apartment_state': 'available',  # Set default state to available
            'default_qty_available': 1.0,  # Ensure quantity is 1
            'force_qty_available': 1.0,  # Force quantity to 1 after save
        }

        domain = [('is_apartment', '=', True), ('building_id', '=', self.id)]

        # Get the action directly instead of using apartment.actions to ensure we get the correct view mode
        action = self.env.ref('wm_real_estate.action_real_estate_apartment_products').read()[0]

        # Update the action with our domain and context
        action['domain'] = domain
        action['context'] = context

        # Explicitly set the view mode to ensure tree view is shown first
        action['view_mode'] = 'tree,form'

        # Get the tree and form views
        tree_view = self.env.ref('wm_real_estate.product_template_apartment_list_view')
        form_view = self.env.ref('wm_real_estate.product_template_form_view_real_estate')

        # Set the views explicitly
        action['views'] = [
            (tree_view.id, 'tree'),
            (form_view.id, 'form')
        ]

        # Add help message
        action['help'] = """<p class="o_view_nocontent_smiling_face">
                        No apartments found for this building
                    </p>
                    <p>
                        Click the create button to add a new apartment.
                    </p>"""

        return action

    def action_view_reservations(self):
        self.ensure_one()
        return {
            'name': _('Reserved Apartments'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_apartment', '=', True),
                ('building_id', '=', self.id),
                ('apartment_state', '=', 'reserved')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_apartment': True,
                'default_building_id': self.id,
                'default_project_id': self.project_id.id,
                'search_default_is_apartment': 1,
                'search_default_reserved_apartments': 1,
                # Make project and building fields read-only
                'default_context_project_readonly': True,
                'default_context_building_readonly': True,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                # Ensure quantity is set correctly
                'default_type': 'product',
                'default_qty_available': 0.0,
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No reserved apartments found for this building
                    </p>"""
        }

    def action_view_sold_apartments(self):
        self.ensure_one()

        return {
            'name': _('Sold Apartments'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_apartment', '=', True),
                ('building_id', '=', self.id),
                ('apartment_state', '=', 'sold')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_apartment': True,
                'default_building_id': self.id,
                'default_project_id': self.project_id.id,
                'search_default_is_apartment': 1,
                'search_default_sold_apartments': 1,
                # Make project and building fields read-only
                'default_context_project_readonly': True,
                'default_context_building_readonly': True,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                # Ensure quantity is set correctly
                'default_type': 'product',
                'default_qty_available': 0.0,
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No sold apartments found for this building
                    </p>"""
        }

    def action_view_available_apartments(self):
        self.ensure_one()

        return {
            'name': _('Available Apartments'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_apartment', '=', True),
                ('building_id', '=', self.id),
                ('apartment_state', '=', 'available')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_apartment': True,
                'default_building_id': self.id,
                'default_project_id': self.project_id.id,
                'search_default_is_apartment': 1,
                'search_default_available_apartments': 1,
                # Make project and building fields read-only
                'default_context_project_readonly': True,
                'default_context_building_readonly': True,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                # Ensure quantity is set to 1 for new apartments
                'default_type': 'product',
                'default_apartment_state': 'available',
                'default_qty_available': 1.0,
                'force_qty_available': 1.0,
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No available apartments found for this building
                    </p>"""
        }

    def action_view_stores(self):
        self.ensure_one()

        # Get all store products for this building
        products = self.env['product.template'].search([
            ('is_store', '=', True),
            ('building_id', '=', self.id)
        ])

        # Log for debugging
        _logger.info("Building %s: Found %s stores", self.name, len(products))

        # Prepare context for the action
        context = {
            'default_is_store': True,
            'default_building_id': self.id,
            'default_project_id': self.project_id.id,
            'search_default_is_store': 1,
            # Make project and building fields read-only
            'default_context_project_readonly': True,
            'default_context_building_readonly': True,
            'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
            'from_button_box': True,
            # Ensure quantity is set correctly
            'default_type': 'product',
            'default_apartment_state': 'available',
            'default_qty_available': 1.0,
            'force_qty_available': 1.0,
        }

        domain = [('is_store', '=', True), ('building_id', '=', self.id)]

        # Get the action directly
        action = self.env.ref('wm_real_estate.action_real_estate_store_products').read()[0]

        # Update the action with our domain and context
        action['domain'] = domain
        action['context'] = context

        # Explicitly set the view mode to ensure tree view is shown first
        action['view_mode'] = 'tree,form'

        # Get the tree and form views
        tree_view = self.env.ref('wm_real_estate.product_template_apartment_list_view')
        form_view = self.env.ref('wm_real_estate.product_template_form_view_real_estate')

        # Set the views explicitly
        action['views'] = [
            (tree_view.id, 'tree'),
            (form_view.id, 'form')
        ]

        # Add help message
        action['help'] = """<p class="o_view_nocontent_smiling_face">
                        No stores found for this building
                    </p>
                    <p>
                        Click the create button to add a new store.
                    </p>"""

        return action

    def action_view_sold_stores(self):
        self.ensure_one()

        return {
            'name': _('Sold Stores'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_store', '=', True),
                ('building_id', '=', self.id),
                ('apartment_state', '=', 'sold')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_store': True,
                'default_building_id': self.id,
                'default_project_id': self.project_id.id,
                'search_default_is_store': 1,
                'search_default_sold_stores': 1,
                # Make project and building fields read-only
                'default_context_project_readonly': True,
                'default_context_building_readonly': True,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                # Ensure quantity is set correctly
                'default_type': 'product',
                'default_apartment_state': 'sold',
                'default_qty_available': 0.0,
                'force_qty_available': 0.0,
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No sold stores found for this building
                    </p>"""
        }

    def action_view_available_stores(self):
        self.ensure_one()

        return {
            'name': _('Available Stores'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_store', '=', True),
                ('building_id', '=', self.id),
                ('apartment_state', '=', 'available')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_store': True,
                'default_building_id': self.id,
                'default_project_id': self.project_id.id,
                'search_default_is_store': 1,
                'search_default_available_stores': 1,
                # Make project and building fields read-only
                'default_context_project_readonly': True,
                'default_context_building_readonly': True,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                # Ensure quantity is set correctly
                'default_type': 'product',
                'default_apartment_state': 'available',
                'default_qty_available': 1.0,
                'force_qty_available': 1.0,
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No available stores found for this building
                    </p>"""
        }

    def action_view_reserved_stores(self):
        self.ensure_one()

        return {
            'name': _('Reserved Stores'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_store', '=', True),
                ('building_id', '=', self.id),
                ('apartment_state', '=', 'reserved')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_store': True,
                'default_building_id': self.id,
                'default_project_id': self.project_id.id,
                'search_default_is_store': 1,
                'search_default_reserved_stores': 1,
                # Make project and building fields read-only
                'default_context_project_readonly': True,
                'default_context_building_readonly': True,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                # Ensure quantity is set correctly
                'default_type': 'product',
                'default_apartment_state': 'reserved',
                'default_qty_available': 0.0,
                'force_qty_available': 0.0,
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No reserved stores found for this building
                    </p>"""
        }
