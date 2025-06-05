from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class RealEstateProject(models.Model):
    _name = 'real.estate.project'
    _description = 'Real Estate Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Project Name', required=True, tracking=True)
    city = fields.Char(string='City', required=True, tracking=True)
    address = fields.Text(string='Address')
    description = fields.Text(string='Description')

    logo = fields.Binary(string='Logo', attachment=True)

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    building_ids = fields.One2many('real.estate.building', 'project_id',
                                   string='Buildings')
    building_count = fields.Integer(compute='_compute_building_count',
                                    string='Building Count')

    apartment_count = fields.Integer(compute='_compute_apartment_count',
                                     string='Apartment Count')

    sold_apartment_count = fields.Integer(compute='_compute_sold_available_apartment_count',
                                     string='Sold Apartments')

    available_apartment_count = fields.Integer(compute='_compute_sold_available_apartment_count',
                                     string='Disponible Apartments')

    reserved_apartment_count = fields.Integer(compute='_compute_sold_available_apartment_count',
                                     string='Préréservé Apartments')

    reservation_count = fields.Integer(compute='_compute_reservation_count',
                                string='Reservation Count')

    # Store-related fields
    store_count = fields.Integer(compute='_compute_store_count',
                                string='Store Count')

    sold_store_count = fields.Integer(compute='_compute_sold_available_store_count',
                                string='Sold Stores')

    available_store_count = fields.Integer(compute='_compute_sold_available_store_count',
                                string='Disponible Stores')

    reserved_store_count = fields.Integer(compute='_compute_sold_available_store_count',
                                string='Préréservé Stores')

    # Équipement-related fields
    equipement_count = fields.Integer(compute='_compute_equipement_count',
                                   string='Équipement Count')

    sold_equipement_count = fields.Integer(compute='_compute_sold_available_equipement_count',
                                        string='Sold Équipements')

    available_equipement_count = fields.Integer(compute='_compute_sold_available_equipement_count',
                                             string='Disponible Équipements')

    reserved_equipement_count = fields.Integer(compute='_compute_sold_available_equipement_count',
                                            string='Préréservé Équipements')

    @api.depends('building_ids')
    def _compute_building_count(self):
        for project in self:
            project.building_count = len(project.building_ids)

    @api.depends('building_ids.apartment_ids', 'building_ids.apartment_ids.product_tmpl_ids')
    def _compute_apartment_count(self):
        for project in self:
            # Count all apartments linked to this project using product.template
            # This ensures consistency with the other count methods
            product_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('project_id', '=', project.id)
            ])

            # For reference, also get the direct count from apartment model
            direct_count = self.env['real.estate.apartment'].search_count(
                [('building_id.project_id', '=', project.id)])

            # Log for debugging
            _logger.info("Project %s: apartment_count=%s (product_count), direct_count=%s",
                        project.name, product_count, direct_count)

            # Use the product count to be consistent with other methods
            project.apartment_count = product_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['apartment_count'], project)

    @api.depends('building_ids.apartment_ids', 'building_ids.apartment_ids.product_tmpl_ids')
    def _compute_sold_available_apartment_count(self):
        for project in self:
            # Count sold apartments for this project
            sold_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'sold')
            ])

            # Count available apartments for this project (exclude blocker status)
            available_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'disponible')
            ])

            # Count reserved apartments for this project
            reserved_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'prereserved')
            ])

            # Count blocked apartments for this project
            blocked_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'blocker')
            ])

            # Calculate total for verification
            total_by_state = sold_count + available_count + reserved_count + blocked_count

            # Get total count for comparison
            total_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('project_id', '=', project.id)
            ])

            # Log for debugging
            _logger.info("Project %s: sold=%s, available=%s, reserved=%s, blocked=%s, total_by_state=%s, total_count=%s",
                        project.name, sold_count, available_count, reserved_count, blocked_count,
                        total_by_state, total_count)

            project.sold_apartment_count = sold_count
            project.available_apartment_count = available_count
            project.reserved_apartment_count = reserved_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['sold_apartment_count'], project)
            self.env.add_to_compute(self._fields['available_apartment_count'], project)
            self.env.add_to_compute(self._fields['reserved_apartment_count'], project)

    @api.depends('building_ids.apartment_ids.state')
    def _compute_reservation_count(self):
        for project in self:
            # Count only apartments with 'prereserved' state in this project
            reservation_count = self.env['product.template'].search_count([
                ('is_apartment', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'prereserved')
            ])

            # Log for debugging
            _logger.info("Project %s: reservation_count=%s", project.name, reservation_count)

            # This should match the reserved_apartment_count field
            project.reservation_count = reservation_count

    @api.depends('building_ids')
    def _compute_store_count(self):
        for project in self:
            # Count all stores linked to this project
            store_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('project_id', '=', project.id)
            ])

            # Log for debugging
            _logger.info("Project %s: store_count=%s", project.name, store_count)

            project.store_count = store_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['store_count'], project)

    @api.depends('building_ids')
    def _compute_sold_available_store_count(self):
        for project in self:
            # Count sold stores for this project
            sold_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'sold')
            ])

            # Count available stores for this project (exclude blocker status)
            available_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'disponible')
            ])

            # Count reserved stores for this project
            reserved_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'prereserved')
            ])

            # Count blocked stores for this project
            blocked_count = self.env['product.template'].search_count([
                ('is_store', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'blocker')
            ])

            # Log for debugging
            _logger.info("Project %s: sold_store_count=%s, available_store_count=%s, reserved_store_count=%s, blocked_store_count=%s",
                        project.name, sold_count, available_count, reserved_count, blocked_count)

            project.sold_store_count = sold_count
            project.available_store_count = available_count
            project.reserved_store_count = reserved_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['sold_store_count'], project)
            self.env.add_to_compute(self._fields['available_store_count'], project)
            self.env.add_to_compute(self._fields['reserved_store_count'], project)

    @api.depends('building_ids')
    def _compute_equipement_count(self):
        for project in self:
            # Count all équipements linked to this project
            equipement_count = self.env['product.template'].search_count([
                ('is_equipement', '=', True),
                ('project_id', '=', project.id)
            ])

            # Log for debugging
            _logger.info("Project %s: equipement_count=%s", project.name, equipement_count)

            project.equipement_count = equipement_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['equipement_count'], project)

    @api.depends('building_ids')
    def _compute_sold_available_equipement_count(self):
        for project in self:
            # Count sold équipements for this project
            sold_count = self.env['product.template'].search_count([
                ('is_equipement', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'sold')
            ])

            # Count available équipements for this project (exclude blocker status)
            available_count = self.env['product.template'].search_count([
                ('is_equipement', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'disponible')
            ])

            # Count reserved équipements for this project
            reserved_count = self.env['product.template'].search_count([
                ('is_equipement', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'prereserved')
            ])

            # Count blocked équipements for this project
            blocked_count = self.env['product.template'].search_count([
                ('is_equipement', '=', True),
                ('project_id', '=', project.id),
                ('apartment_state', '=', 'blocker')
            ])

            # Log for debugging
            _logger.info("Project %s: sold_equipement_count=%s, available_equipement_count=%s, reserved_equipement_count=%s, blocked_equipement_count=%s",
                        project.name, sold_count, available_count, reserved_count, blocked_count)

            project.sold_equipement_count = sold_count
            project.available_equipement_count = available_count
            project.reserved_equipement_count = reserved_count

            # Force cache invalidation
            self.env.add_to_compute(self._fields['sold_equipement_count'], project)
            self.env.add_to_compute(self._fields['available_equipement_count'], project)
            self.env.add_to_compute(self._fields['reserved_equipement_count'], project)

    def action_view_buildings(self):
        self.ensure_one()
        return {
            'name': _('Buildings'),
            'view_mode': 'tree,form',
            'res_model': 'real.estate.building',
            'domain': [('project_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {
                'default_project_id': self.id,
                'default_context_project_readonly': True
            }
        }

    def action_view_apartments(self):
        self.ensure_one()

        # Get all apartments for this project
        apartments = self.env['real.estate.apartment'].search([
            ('building_id.project_id', '=', self.id)
        ])

        # Get all apartment products for this project
        products = self.env['product.template'].search([
            ('is_apartment', '=', True),
            ('project_id', '=', self.id)
        ])

        # Log for debugging
        _logger.info("Project %s: Found %s apartments and %s products",
                    self.name, len(apartments), len(products))

        # Use the apartment actions model to get the action
        context = {
            'default_is_apartment': True,
            'default_project_id': self.id,
            'default_building_id': self.building_ids[0].id if self.building_ids else False,
            'search_default_is_apartment': 1,
            'search_default_groupby_building': 1,  # Group by building
            # Make project field read-only but building field editable
            'default_context_project_readonly': True,
            'default_context_building_readonly': False,
            'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',  # Ensure it uses the correct form view
            'from_button_box': True,  # Flag to indicate this is from button box
            'from_project_view': True,  # Special flag to ensure building field is editable
            'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
            # Ensure the create button is available and that new apartments have quantity 1
            'create': True,
            'default_apartment_state': 'disponible',
            'default_type': 'product',
            'default_qty_available': 1.0,
            'force_qty_available': 1.0,
        }

        domain = [('is_apartment', '=', True), ('project_id', '=', self.id)]

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
                        No apartments found for this project
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
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'reserved')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_apartment': True,
                'default_project_id': self.id,
                'search_default_is_apartment': 1,
                'search_default_reserved_apartments': 1,
                'search_default_groupby_building': 1,  # Group by building
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,  # Make building field editable
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No reserved apartments found for this project
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
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'sold')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_apartment': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_apartment': 1,
                'search_default_sold_apartments': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No sold apartments found for this project
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
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'disponible')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_apartment': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_apartment': 1,
                'search_default_available_apartments': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
                'default_apartment_state': 'disponible',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No available apartments found for this project
                    </p>"""
        }

    def action_view_stores(self):
        self.ensure_one()

        # Get all store products for this project
        products = self.env['product.template'].search([
            ('is_store', '=', True),
            ('project_id', '=', self.id)
        ])

        # Log for debugging
        _logger.info("Project %s: Found %s stores", self.name, len(products))

        # Prepare context for the action
        context = {
            'default_is_store': True,
            'default_project_id': self.id,
            'default_building_id': self.building_ids[0].id if self.building_ids else False,
            'search_default_is_store': 1,
            'search_default_groupby_building': 1,  # Group by building
            # Make project field read-only but building field editable
            'default_context_project_readonly': True,
            'default_context_building_readonly': False,
            'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
            'from_button_box': True,
            'from_project_view': True,  # Special flag to ensure building field is editable
            'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
            # Quantity management is now handled by Odoo's standard inventory management
            'default_type': 'product',
            'default_apartment_state': 'disponible',
        }

        domain = [('is_store', '=', True), ('project_id', '=', self.id)]

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
                        No stores found for this project
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
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'sold')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_store': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_store': 1,
                'search_default_sold_stores': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
                'default_apartment_state': 'sold',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No sold stores found for this project
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
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'available')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_store': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_store': 1,
                'search_default_available_stores': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
                'default_apartment_state': 'available',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No available stores found for this project
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
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'reserved')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_store': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_store': 1,
                'search_default_reserved_stores': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
                'default_apartment_state': 'reserved',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No reserved stores found for this project
                    </p>"""
        }

    # Équipement action methods
    def action_view_equipements(self):
        self.ensure_one()

        # Get all équipement products for this project
        products = self.env['product.template'].search([
            ('is_equipement', '=', True),
            ('project_id', '=', self.id)
        ])

        # Log for debugging
        _logger.info("Project %s: Found %s équipements", self.name, len(products))

        # Prepare context for the action
        context = {
            'default_is_equipement': True,
            'default_project_id': self.id,
            'default_building_id': self.building_ids[0].id if self.building_ids else False,
            'search_default_is_equipement': 1,
            'search_default_groupby_building': 1,  # Group by building
            # Make project field read-only but building field editable
            'default_context_project_readonly': True,
            'default_context_building_readonly': False,
            'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
            'from_button_box': True,
            'from_project_view': True,  # Special flag to ensure building field is editable
            'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
            # Quantity management is now handled by Odoo's standard inventory management
            'default_type': 'product',
            'default_apartment_state': 'disponible',
        }

        domain = [('is_equipement', '=', True), ('project_id', '=', self.id)]

        # Get the action directly
        action = self.env.ref('wm_real_estate.action_real_estate_equipement_products').read()[0]

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
                        No équipements found for this project
                    </p>
                    <p>
                        Click the create button to add a new équipement.
                    </p>"""

        return action

    def action_view_sold_equipements(self):
        self.ensure_one()

        return {
            'name': _('Sold Équipements'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_equipement', '=', True),
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'sold')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_equipement': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_equipement': 1,
                'search_default_sold_equipements': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
                'default_apartment_state': 'sold',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No sold équipements found for this project
                    </p>"""
        }

    def action_view_available_equipements(self):
        self.ensure_one()

        return {
            'name': _('Available Équipements'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_equipement', '=', True),
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'disponible')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_equipement': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_equipement': 1,
                'search_default_available_equipements': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
                'default_apartment_state': 'disponible',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No available équipements found for this project
                    </p>"""
        }

    def action_view_reserved_equipements(self):
        self.ensure_one()

        return {
            'name': _('Reserved Équipements'),
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'domain': [
                ('is_equipement', '=', True),
                ('project_id', '=', self.id),
                ('apartment_state', '=', 'reserved')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_is_equipement': True,
                'default_project_id': self.id,
                'default_building_id': self.building_ids[0].id if self.building_ids else False,
                'search_default_is_equipement': 1,
                'search_default_reserved_equipements': 1,
                'search_default_groupby_building': 1,  # Group by building
                # Make project field read-only but building field editable
                'default_context_project_readonly': True,
                'default_context_building_readonly': False,
                'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate',
                'from_button_box': True,
                'from_project_view': True,  # Special flag to ensure building field is editable
                'force_building_editable': True,  # CRITICAL FIX: Force building field to be editable
                # Quantity management is now handled by Odoo's standard inventory management
                'default_type': 'product',
                'default_apartment_state': 'reserved',
            },
            'help': """<p class="o_view_nocontent_smiling_face">
                        No reserved équipements found for this project
                    </p>"""
        }
