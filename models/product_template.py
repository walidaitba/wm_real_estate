from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import time

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Real Estate specific fields
    is_apartment = fields.Boolean(string='Is Apartment', default=False)
    is_store = fields.Boolean(string='Is Store', default=False)
    is_equipement = fields.Boolean(string='Is Équipement', default=False)
    apartment_id = fields.Many2one('real.estate.apartment', string='Apartment')

    # Direct fields for apartment/store/équipement properties
    floor = fields.Integer(string='Floor')
    area = fields.Float(string='Area (m²)')
    rooms = fields.Integer(string='Number of Rooms', default=1)
    bathrooms = fields.Integer(string='Number of Bathrooms', default=1)

    # Building and Project information
    building_id = fields.Many2one('real.estate.building', string='Building')
    project_id = fields.Many2one('real.estate.project', string='Project')

    # Context fields for form behavior
    context_project_readonly = fields.Boolean(string='Project Readonly', default=False,
                                            help="Technical field to make project field readonly based on context")
    context_building_readonly = fields.Boolean(string='Building Readonly', default=False,
                                             help="Technical field to make building field readonly based on context")

    # State for apartments - computed from apartment's actual state
    apartment_state = fields.Selection([
        ('disponible', 'Disponible'),
        ('prereserved', 'Préréservé'),
        ('sold', 'Vendu'),
        ('blocker', 'Bloqué'),
    ], string='Apartment Status', compute='_compute_apartment_state', inverse='_inverse_apartment_state', 
       store=True, readonly=False, default='disponible', required=True,
       help="Status of the apartment. This field is synchronized with the apartment record.")

    # Locking mechanism fields
    is_locked = fields.Boolean(string='Locked', related='apartment_id.is_locked', readonly=True,
                              help="Indicates if the apartment is locked for a quotation")
    locked_by_order_id = fields.Many2one('sale.order', string='Locked By Order',
                                       related='apartment_id.locked_by_order_id', readonly=True,
                                       help="The quotation that has locked this apartment")
    lock_date = fields.Datetime(string='Lock Date', related='apartment_id.lock_date', readonly=True,
                              help="Date and time when the apartment was locked")

    @api.depends('apartment_id.state', 'is_apartment', 'is_store', 'is_equipement', 'sale_ok')
    def _compute_apartment_state(self):
        """Compute apartment state from the linked apartment record"""
        for product in self:
            # First check if sale_ok is False - this overrides all other states
            if not product.sale_ok and (product.is_apartment or product.is_store or product.is_equipement):
                product.apartment_state = 'blocker'
            elif product.is_apartment and product.apartment_id:
                # For apartments, get the state from the linked apartment (unless blocked)
                if product.sale_ok:
                    product.apartment_state = product.apartment_id.state
                else:
                    product.apartment_state = 'blocker'
            elif product.is_store or product.is_equipement:
                # For stores and équipement, use the stored value or default to disponible (unless blocked)
                if product.sale_ok:
                    if not product.apartment_state or product.apartment_state == 'blocker':
                        product.apartment_state = 'disponible'
                else:
                    product.apartment_state = 'blocker'
            else:
                # For non-real estate products, set to disponible
                product.apartment_state = 'disponible'

    def _inverse_apartment_state(self):
        """Update apartment state when changed from product side"""
        for product in self:
            # Handle blocker status - update sale_ok field
            if product.apartment_state == 'blocker':
                product.sale_ok = False
            elif product.apartment_state in ['disponible', 'prereserved', 'sold']:
                # Only set sale_ok to True if it was previously False due to blocker
                if not product.sale_ok:
                    product.sale_ok = True
            
            if product.is_apartment and product.apartment_id:
                # Don't sync blocker status to apartment record - it's product-level only
                if product.apartment_state != 'blocker':
                    # Update the linked apartment's state
                    product.apartment_id.with_context(from_product_update=True).write({
                        'state': product.apartment_state
                    })
                    _logger.info("Updated apartment %s state to %s from product", 
                               product.apartment_id.name, product.apartment_state)

    @api.model
    def default_get(self, fields_list):
        """Override default_get to set readonly flags based on context"""
        res = super(ProductTemplate, self).default_get(fields_list)

        # Log the context for debugging
        _logger.info("DEBUG_APARTMENT_CREATION: default_get context: %s", self.env.context)
        _logger.info("DEBUG_APARTMENT_CREATION: default_get called from: %s",
                    "project_view" if self.env.context.get('from_project_view') else
                    "button_box" if self.env.context.get('from_button_box') else
                    "notebook" if self.env.context.get('from_notebook') else
                    "menu" if self.env.context.get('from_menu') else
                    "apartment_list" if self.env.context.get('from_apartment_list') else
                    "unknown")

        # CASE 1: Creating from a building
        if self.env.context.get('default_building_id'):
            # When creating from a building, both building and project should be read-only
            res['context_building_readonly'] = True
            res['context_project_readonly'] = True
            _logger.info("Creating from building: Setting building_readonly=True and project_readonly=True")

            # Get the project_id from the building
            try:
                building = self.env['real.estate.building'].browse(self.env.context.get('default_building_id'))
                if building and building.project_id:
                    res['project_id'] = building.project_id.id
                    _logger.info("Setting project_id=%s from building %s",
                                building.project_id.id, building.name)
            except Exception as e:
                _logger.error("Error getting project from building: %s", str(e))

        # CASE 2: Creating from a project
        elif self.env.context.get('default_project_id'):
            # When creating from a project, project should be read-only but building should be editable
            res['context_project_readonly'] = True
            res['context_building_readonly'] = False

            # SPECIAL CASE: Explicitly check if we're coming from project view
            if self.env.context.get('from_project_view'):
                _logger.info("Creating from project view: Ensuring building_readonly=False")
                res['context_building_readonly'] = False

            _logger.info("Creating from project: Setting project_readonly=True and building_readonly=False")

        # CASE 3: Creating from apartments page (neither default_building_id nor default_project_id)
        else:
            # When creating from apartments page, both fields should be editable
            res['context_project_readonly'] = False
            res['context_building_readonly'] = False
            _logger.info("Creating from apartments page: Both project and building are editable")

        # Also check for force_building_id context
        if self.env.context.get('force_building_id'):
            res['context_building_readonly'] = True
            _logger.info("Setting building_readonly=True from force_building_id=%s",
                        self.env.context.get('force_building_id'))

            # Get the building and its project
            try:
                building = self.env['real.estate.building'].browse(self.env.context.get('force_building_id'))
                if building and building.exists():
                    res['building_id'] = building.id
                    if building.project_id:
                        res['project_id'] = building.project_id.id
                        res['context_project_readonly'] = True
                        _logger.info("Setting project_id=%s and project_readonly=True from force_building_id",
                                    building.project_id.id)
            except Exception as e:
                _logger.error("Error getting building from force_building_id: %s", str(e))

        # Check if we're coming from a specific action
        if self.env.context.get('from_button_box'):
            _logger.info("Creating apartment product from button box action")

            # SPECIAL CASE: If we're coming from a project's button box
            if self.env.context.get('from_project_view'):
                _logger.info("Creating apartment from project's button box in default_get")
                # Ensure building field is editable when creating from project view
                res['context_building_readonly'] = False

        elif self.env.context.get('from_notebook'):
            _logger.info("Creating apartment product from building notebook")
        elif self.env.context.get('from_menu'):
            _logger.info("Creating apartment product from menu action")
        elif self.env.context.get('from_apartment_list'):
            _logger.info("Creating apartment product from apartment list")

        # Log for debugging
        _logger.info("DEBUG_APARTMENT_CREATION: default_get result: project_readonly=%s, building_readonly=%s",
                    res.get('context_project_readonly'), res.get('context_building_readonly'))

        # CRITICAL DEBUG: Force building to be editable when coming from project view
        if self.env.context.get('from_project_view') or self.env.context.get('force_building_editable'):
            res['context_building_readonly'] = False
            _logger.info("DEBUG_APARTMENT_CREATION: FORCING building_readonly=False in default_get for project view or force_building_editable")

        # Final check of readonly flags
        _logger.info("DEBUG_APARTMENT_CREATION: FINAL default_get result: project_readonly=%s, building_readonly=%s",
                    res.get('context_project_readonly'), res.get('context_building_readonly'))

        return res

    @api.onchange('is_apartment')
    def _onchange_is_apartment(self):
        """When marking as apartment, set product type to storable and update name placeholder"""
        if self.is_apartment:
            # If is_store or is_equipement is also checked, uncheck them (mutual exclusivity)
            if self.is_store:
                self.is_store = False
            if self.is_equipement:
                self.is_equipement = False

            # Log the context for debugging
            _logger.info("DEBUG_APARTMENT_CREATION: _onchange_is_apartment context: %s", self.env.context)
            _logger.info("DEBUG_APARTMENT_CREATION: _onchange_is_apartment called from: %s",
                        "project_view" if self.env.context.get('from_project_view') else
                        "button_box" if self.env.context.get('from_button_box') else
                        "notebook" if self.env.context.get('from_notebook') else
                        "menu" if self.env.context.get('from_menu') else
                        "apartment_list" if self.env.context.get('from_apartment_list') else
                        "unknown")

            self.type = 'product'  # Storable product
            # If this is a new record with no name yet, set a default name
            if not self.name or self.name == 'New Product':
                self.name = 'New Apartment'

            # Log initial readonly state
            _logger.info("DEBUG_APARTMENT_CREATION: _onchange_is_apartment INITIAL: project_readonly=%s, building_readonly=%s",
                        self.context_project_readonly, self.context_building_readonly)

            # Set readonly flags based on context
            # CASE 1: Creating from a building
            if self.env.context.get('default_building_id'):
                # When creating from a building, both building and project should be read-only
                self.context_building_readonly = True
                self.context_project_readonly = True

            # CASE 2: Creating from a project
            elif self.env.context.get('default_project_id'):
                # When creating from a project, project should be read-only but building should be editable
                self.context_project_readonly = True
                self.context_building_readonly = False

                # SPECIAL CASE: Explicitly mark as coming from project view
                if self.env.context.get('from_project_view'):
                    _logger.info("Creating from project view: Ensuring building_readonly=False")
                    self.context_building_readonly = False

                    # CRITICAL FIX: Force building to be editable even when coming from button box
                    if self.env.context.get('from_button_box'):
                        _logger.info("Creating from project's button box in _onchange_is_apartment: Forcing building_readonly=False")
                        self.context_building_readonly = False

            # CASE 3: Creating from apartments page (neither default_building_id nor default_project_id)
            else:
                # When creating from apartments page, both fields should be editable
                self.context_project_readonly = False
                self.context_building_readonly = False

            # Override for force_building_id
            if self.env.context.get('force_building_id'):
                self.context_building_readonly = True

            # CRITICAL DEBUG: Force building to be editable when coming from project view
            if self.env.context.get('from_project_view') or self.env.context.get('force_building_editable'):
                self.context_building_readonly = False
                _logger.info("DEBUG_APARTMENT_CREATION: FORCING building_readonly=False in _onchange_is_apartment for project view or force_building_editable")

            # Log final readonly state
            _logger.info("DEBUG_APARTMENT_CREATION: _onchange_is_apartment FINAL: project_readonly=%s, building_readonly=%s",
                        self.context_project_readonly, self.context_building_readonly)

    # The _onchange_building_id_floor method has been removed as it was redundant and causing conflicts
    # Apartment name generation is now handled in _onchange_building_id and create methods

    @api.onchange('is_store')
    def _onchange_is_store(self):
        """When marking as store, set product type to storable and update name placeholder"""
        if self.is_store:
            # If is_apartment or is_equipement is also checked, uncheck them (mutual exclusivity)
            if self.is_apartment:
                self.is_apartment = False
            if self.is_equipement:
                self.is_equipement = False

            self.type = 'product'  # Storable product
            # If this is a new record with no name yet, set a default name
            if not self.name or self.name == 'New Product':
                self.name = 'New Store'

            # Set readonly flags based on context - same logic as apartments
            # CASE 1: Creating from a building
            if self.env.context.get('default_building_id'):
                # When creating from a building, both building and project should be read-only
                self.context_building_readonly = True
                self.context_project_readonly = True

            # CASE 2: Creating from a project
            elif self.env.context.get('default_project_id'):
                # When creating from a project, project should be read-only but building should be editable
                self.context_project_readonly = True
                self.context_building_readonly = False

                # SPECIAL CASE: Explicitly mark as coming from project view
                if self.env.context.get('from_project_view'):
                    _logger.info("Creating from project view: Ensuring building_readonly=False")
                    self.context_building_readonly = False

            # CASE 3: Creating from stores page (neither default_building_id nor default_project_id)
            else:
                # When creating from stores page, both fields should be editable
                self.context_project_readonly = False
                self.context_building_readonly = False

            # Override for force_building_id
            if self.env.context.get('force_building_id'):
                self.context_building_readonly = True

            # CRITICAL DEBUG: Force building to be editable when coming from project view
            if self.env.context.get('from_project_view') or self.env.context.get('force_building_editable'):
                self.context_building_readonly = False

    @api.onchange('is_equipement')
    def _onchange_is_equipement(self):
        """When marking as équipement, set product type to storable and update name placeholder"""
        if self.is_equipement:
            # If is_apartment or is_store is also checked, uncheck them (mutual exclusivity)
            if self.is_apartment:
                self.is_apartment = False
            if self.is_store:
                self.is_store = False

            self.type = 'product'  # Storable product
            # If this is a new record with no name yet, set a default name
            if not self.name or self.name == 'New Product':
                self.name = 'New Équipement'

            # Set readonly flags based on context - same logic as apartments and stores
            # CASE 1: Creating from a building
            if self.env.context.get('default_building_id'):
                # When creating from a building, both building and project should be read-only
                self.context_building_readonly = True
                self.context_project_readonly = True

            # CASE 2: Creating from a project
            elif self.env.context.get('default_project_id'):
                # When creating from a project, project should be read-only but building should be editable
                self.context_project_readonly = True
                self.context_building_readonly = False

                # SPECIAL CASE: Explicitly mark as coming from project view
                if self.env.context.get('from_project_view'):
                    _logger.info("Creating from project view: Ensuring building_readonly=False")
                    self.context_building_readonly = False

            # CASE 3: Creating from équipement page (neither default_building_id nor default_project_id)
            else:
                # When creating from équipement page, both fields should be editable
                self.context_project_readonly = False
                self.context_building_readonly = False

            # Override for force_building_id
            if self.env.context.get('force_building_id'):
                self.context_building_readonly = True

            # CRITICAL DEBUG: Force building to be editable when coming from project view
            if self.env.context.get('from_project_view') or self.env.context.get('force_building_editable'):
                self.context_building_readonly = False

    @api.onchange('apartment_state')
    def _onchange_apartment_state(self):
        """When apartment state changes, schedule inventory update after save"""
        if self.is_apartment:
            # Log the state change
            _logger.info("Apartment state changed to %s for apartment %s", self.apartment_state, self.name)

            # Quantity management is now handled by Odoo's standard inventory management

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """When project changes, reset building and update domain"""
        # Check if we have a forced building_id from context
        force_building_id = self.env.context.get('force_building_id')
        if force_building_id:
            # If we have a forced building_id, use it regardless of project change
            building = self.env['real.estate.building'].browse(force_building_id)
            if building.exists():
                self.building_id = building.id
                # Also set the project to match the building's project
                if building.project_id:
                    self.project_id = building.project_id.id
                    # Set category to match project
                    project_categ = self._get_or_create_project_category(building.project_id)
                    if project_categ:
                        self.categ_id = project_categ.id
                # Log for debugging
                _logger.info("Using forced building_id %s from context", building.name)
                # Return domain to filter buildings by project
                return {'domain': {'building_id': [('project_id', '=', building.project_id.id)]}}

        if self.project_id:
            # If no forced building_id, proceed with normal logic

            # Check if we should reset building
            # Only reset if not coming from a forced context
            if not force_building_id:
                self.building_id = False

            # Set category to match project
            project_categ = self._get_or_create_project_category(self.project_id)
            if project_categ:
                self.categ_id = project_categ.id

            # If there's only one building for this project, auto-select it
            buildings = self.env['real.estate.building'].search([
                ('project_id', '=', self.project_id.id)
            ])
            if len(buildings) == 1:
                self.building_id = buildings.id
            elif not buildings:
                # Don't create a default building, just log a message
                _logger.info("No buildings found for project %s. Please create a building first.", self.project_id.name)

            # Return domain to filter buildings by project
            return {'domain': {'building_id': [('project_id', '=', self.project_id.id)]}}
        else:
            # If no project is selected, don't filter buildings
            return {'domain': {'building_id': []}}

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """When building changes, update project if needed"""
        # Log the context for debugging
        _logger.info("DEBUG_APARTMENT_CREATION: _onchange_building_id context: %s", self.env.context)
        _logger.info("DEBUG_APARTMENT_CREATION: _onchange_building_id called from: %s",
                    "project_view" if self.env.context.get('from_project_view') else
                    "button_box" if self.env.context.get('from_button_box') else
                    "notebook" if self.env.context.get('from_notebook') else
                    "menu" if self.env.context.get('from_menu') else
                    "apartment_list" if self.env.context.get('from_apartment_list') else
                    "unknown")

        # Log initial readonly state
        _logger.info("DEBUG_APARTMENT_CREATION: _onchange_building_id INITIAL: project_readonly=%s, building_readonly=%s",
                    self.context_project_readonly, self.context_building_readonly)

        if self.building_id:
            # Update project if it doesn't match
            if not self.project_id or self.project_id.id != self.building_id.project_id.id:
                self.project_id = self.building_id.project_id.id

                # SPECIAL CASE: Creating from a project
                # When creating from a project, we want to keep the building field editable
                if self.env.context.get('from_project_view'):
                    # When creating from a project, project should be read-only but building should be editable
                    self.context_project_readonly = True
                    self.context_building_readonly = False
                    _logger.info("Creating from project: Setting project_readonly=True and building_readonly=False")

                    # CRITICAL FIX: Force building to be editable even when coming from button box
                    if self.env.context.get('from_button_box'):
                        _logger.info("Creating from project's button box: Forcing building_readonly=False")
                        self.context_building_readonly = False

                # Only set project readonly if we're not in the main apartments page
                elif self.env.context.get('default_building_id') or self.env.context.get('from_button_box'):
                    self.context_project_readonly = True
                    _logger.info("Setting project to %s based on building %s and making it readonly",
                                self.building_id.project_id.name, self.building_id.name)
                else:
                    # When creating from main apartments page, keep project editable
                    _logger.info("Setting project to %s based on building %s but keeping it editable",
                                self.building_id.project_id.name, self.building_id.name)

            # Set category to match building
            building_categ = self._get_or_create_building_category(self.building_id)
            if building_categ:
                self.categ_id = building_categ.id

            # Apartment name generation has been removed from here
            # The name will be set in the create method instead
            _logger.info("Apartment name will be set during creation, not in _onchange_building_id")

            # Don't restrict the project_id domain - allow selecting any project
            # This allows users to change the project even after selecting a building

            # CRITICAL DEBUG: Force building to be editable when coming from project view
            if self.env.context.get('from_project_view') or self.env.context.get('force_building_editable'):
                self.context_building_readonly = False
                _logger.info("DEBUG_APARTMENT_CREATION: FORCING building_readonly=False in _onchange_building_id for project view or force_building_editable")

            # Log final readonly state
            _logger.info("DEBUG_APARTMENT_CREATION: _onchange_building_id FINAL: project_readonly=%s, building_readonly=%s",
                        self.context_project_readonly, self.context_building_readonly)

    @api.onchange('apartment_id')
    def _onchange_apartment_id(self):
        """When apartment is selected, update all fields"""
        if self.apartment_id:
            self.is_apartment = True
            self.name = self.apartment_id.name
            self.default_code = self.apartment_id.code
            self.list_price = self.apartment_id.price
            self.floor = self.apartment_id.floor
            self.area = self.apartment_id.area
            self.rooms = self.apartment_id.rooms
            self.bathrooms = self.apartment_id.bathrooms
            self.building_id = self.apartment_id.building_id.id
            self.project_id = self.apartment_id.project_id.id
            self.apartment_state = self.apartment_id.state
            self.description = self.apartment_id.description

            # Set category based on building
            building_categ = self._get_or_create_building_category(self.apartment_id.building_id)
            if building_categ:
                self.categ_id = building_categ.id

    @api.model
    def create(self, vals):
        """Override create to handle apartment creation"""
        # Log the context and values for debugging
        _logger.info("DEBUG_APARTMENT_CREATION: create context: %s", self.env.context)
        _logger.info("DEBUG_APARTMENT_CREATION: create vals: %s", vals)
        _logger.info("DEBUG_APARTMENT_CREATION: create called from: %s",
                    "project_view" if self.env.context.get('from_project_view') else
                    "button_box" if self.env.context.get('from_button_box') else
                    "notebook" if self.env.context.get('from_notebook') else
                    "menu" if self.env.context.get('from_menu') else
                    "apartment_list" if self.env.context.get('from_apartment_list') else
                    "unknown")

        # Check readonly flags in vals
        _logger.info("DEBUG_APARTMENT_CREATION: create INITIAL: context_project_readonly=%s, context_building_readonly=%s",
                    vals.get('context_project_readonly'), vals.get('context_building_readonly'))

        # Check if we're being called from apartment create to avoid infinite recursion
        if self.env.context.get('from_apartment_create'):
            _logger.info("Creating product from apartment - skipping apartment creation logic")
            return super(ProductTemplate, self).create(vals)

        # If creating an apartment product without linking to existing apartment
        if vals.get('is_apartment') and not vals.get('apartment_id'):
            # CRITICAL FIX: If we don't have a name, generate a temporary one
            # This will be replaced with the proper apartment number once we have a building
            if not vals.get('name'):
                vals['name'] = f"Apartment {int(time.time()) % 10000}"
                _logger.info("CRITICAL FIX: Generated temporary apartment name: %s", vals['name'])

            # Make sure we have a price
            if not vals.get('list_price'):
                vals['list_price'] = 0.0

        # If creating a store product
        elif vals.get('is_store'):
            # If we don't have a name, generate a temporary one
            if not vals.get('name'):
                vals['name'] = f"Store {int(time.time()) % 10000}"
                _logger.info("Generated temporary store name: %s", vals['name'])

            # Make sure we have a price
            if not vals.get('list_price'):
                vals['list_price'] = 0.0

            # Quantity management is now handled by Odoo's standard inventory management
            _logger.info("Quantity will be managed by Odoo's standard inventory system")

        # If creating an équipement product
        elif vals.get('is_equipement'):
            # If we don't have a name, generate a temporary one
            if not vals.get('name'):
                vals['name'] = f"Équipement {int(time.time()) % 10000}"
                _logger.info("Generated temporary équipement name: %s", vals['name'])

            # Make sure we have a price
            if not vals.get('list_price'):
                vals['list_price'] = 0.0

            # Quantity management is now handled by Odoo's standard inventory management
            _logger.info("Quantity will be managed by Odoo's standard inventory system")

            # Check if we have a forced building_id from context
            force_building_id = self.env.context.get('force_building_id')
            if force_building_id:
                # If we have a forced building_id, use it
                building = self.env['real.estate.building'].browse(force_building_id)
                if building.exists():
                    vals['building_id'] = building.id
                    # Also set the project to match the building's project
                    if building.project_id:
                        vals['project_id'] = building.project_id.id
                    # Log for debugging
                    _logger.info("Using forced building_id %s from context during create", building.name)

            # Check for specific creation scenarios
            creation_source = None
            if self.env.context.get('from_button_box'):
                creation_source = "button_box"

                # SPECIAL CASE: If we're coming from a project's button box
                if self.env.context.get('from_project_view'):
                    _logger.info("DEBUG_APARTMENT_CREATION: Creating apartment from project's button box")
                    # Ensure building field is editable when creating from project view
                    vals['context_building_readonly'] = False
                    # CRITICAL FIX: Force building to be editable
                    _logger.info("DEBUG_APARTMENT_CREATION: FORCING context_building_readonly=False in create for project view")

            elif self.env.context.get('from_notebook'):
                creation_source = "notebook"
            elif self.env.context.get('from_menu'):
                creation_source = "menu"
            elif self.env.context.get('from_apartment_list'):
                creation_source = "apartment_list"

            if creation_source:
                _logger.info("Creating apartment from %s", creation_source)

            # If no building_id yet, try to find one based on project_id
            if not vals.get('building_id') and vals.get('project_id'):
                # Try to find a building for this project
                building = self.env['real.estate.building'].search([
                    ('project_id', '=', vals.get('project_id'))
                ], limit=1)

                if building:
                    vals['building_id'] = building.id
                    _logger.info("Auto-selected building %s for project %s", building.name, vals.get('project_id'))
                else:
                    # Don't create a default building, just log a message
                    _logger.info("No building found for project ID %s. Please select a building.", vals.get('project_id'))

            # If we don't have a building_id, we can't create an apartment
            if not vals.get('building_id'):
                _logger.warning("Cannot create apartment without building_id. Please select a building first.")
                # Set is_apartment to False to prevent apartment creation
                vals['is_apartment'] = False
                _logger.info("Setting is_apartment to False due to missing building_id")

            # Now create the apartment
            apartment_vals = self._prepare_apartment_vals(vals)
            if apartment_vals:
                try:
                    # Check if we're using an existing apartment
                    if 'existing_id' in apartment_vals:
                        # Use the existing apartment instead of creating a new one
                        vals['apartment_id'] = apartment_vals['existing_id']
                        _logger.info("Using existing apartment with ID %s", apartment_vals['existing_id'])
                    else:
                        # Create a new apartment with context to prevent circular reference
                        _logger.info("Creating new apartment with vals: %s", apartment_vals)
                        apartment = self.env['real.estate.apartment'].with_context(from_product_create=True).create(apartment_vals)
                        vals['apartment_id'] = apartment.id
                        _logger.info("Created apartment %s from product with ID %s", apartment.name, apartment.id)
                except Exception as e:
                    _logger.error("Error creating apartment from product: %s", str(e))
            else:
                _logger.warning("Could not prepare apartment values. Missing building_id or project_id.")

        # CRITICAL FIX: Force building to be editable when coming from project view
        if self.env.context.get('from_project_view') or self.env.context.get('force_building_editable'):
            vals['context_building_readonly'] = False
            _logger.info("DEBUG_APARTMENT_CREATION: FINAL FORCING context_building_readonly=False in create for project view or force_building_editable")

        # Log final readonly flags before create
        _logger.info("DEBUG_APARTMENT_CREATION: create FINAL: context_project_readonly=%s, context_building_readonly=%s",
                    vals.get('context_project_readonly'), vals.get('context_building_readonly'))

        # Only generate a name if the user hasn't entered one or if it's a default name
        default_names = ['New Apartment', 'New Product', f"Apartment {int(time.time()) % 10000}"]
        if vals.get('is_apartment') and vals.get('building_id') and vals.get('floor') is not None and (not vals.get('name') or vals.get('name') in default_names):
            try:
                # Get the building
                building = self.env['real.estate.building'].browse(vals.get('building_id'))
                if building.exists():
                    # Count existing apartments on this floor in this building
                    floor = vals.get('floor', 0)
                    existing_count = self.env['real.estate.apartment'].search_count([
                        ('building_id', '=', building.id),
                        ('floor', '=', floor)
                    ])

                    # Generate apartment number
                    building_prefix = building.code[0].upper() if building.code else 'A'
                    apt_number = f"{building_prefix}{floor:02d}{existing_count+1:02d}"

                    # Set the name to "Apartment" followed by the number only if user hasn't entered a custom name
                    vals['name'] = f"Apartment {apt_number}"
                    vals['default_code'] = apt_number

                    _logger.info("Pre-create - Generated apartment name %s", vals['name'])
            except Exception as e:
                _logger.error("Error formatting apartment name before create: %s", str(e))
        else:
            _logger.info("Pre-create - Keeping user-entered apartment name: %s", vals.get('name'))

        # Call super to create the product
        res = super(ProductTemplate, self).create(vals)

        # After creation, ensure the apartment is properly linked
        if res.is_apartment and res.apartment_id:
            try:
                # Only generate a name if the user hasn't entered one or if it's a default name
                default_names = ['New Apartment', 'New Product', f"Apartment {int(time.time()) % 10000}"]
                if res.building_id and res.floor is not None and (not res.name or res.name in default_names):
                    # Count existing apartments on this floor in this building
                    floor = res.floor or 0
                    existing_count = self.env['real.estate.apartment'].search_count([
                        ('building_id', '=', res.building_id.id),
                        ('floor', '=', floor)
                    ])

                    # Generate apartment number
                    building_prefix = res.building_id.code[0].upper() if res.building_id.code else 'A'
                    apt_number = f"{building_prefix}{floor:02d}{existing_count:02d}"  # Use existing_count without +1

                    # Set the name to "Apartment" followed by the number only if user hasn't entered a custom name
                    suggested_name = f"Apartment {apt_number}"
                    res.name = suggested_name
                    res.default_code = f"APT-{apt_number}"
                    _logger.info("Generated apartment name %s for new apartment", suggested_name)
                else:
                    _logger.info("Keeping user-entered apartment name: %s", res.name)

                # Quantity management is now handled by Odoo's standard inventory management
                _logger.info("Quantity for new apartment %s will be managed by Odoo's standard inventory system",
                            res.name)

                # Update the apartment with any missing information
                update_vals = {}

                # Make sure building is set
                if res.building_id and (not res.apartment_id.building_id or res.apartment_id.building_id.id != res.building_id.id):
                    update_vals['building_id'] = res.building_id.id
                    _logger.info("Updating apartment building to %s", res.building_id.name)

                # Update price if needed
                if res.list_price and res.apartment_id.price != res.list_price:
                    update_vals['price'] = res.list_price

                # Update other fields if needed
                for field in ['name', 'floor', 'area', 'rooms', 'bathrooms']:
                    if getattr(res, field) and getattr(res.apartment_id, field) != getattr(res, field):
                        update_vals[field] = getattr(res, field)

                if update_vals:
                    res.apartment_id.write(update_vals)
                    _logger.info("Updated apartment %s with additional info: %s",
                                res.apartment_id.name, update_vals)

                    # Invalidate cache to ensure related fields are updated
                    res.apartment_id.invalidate_cache()
                    res.invalidate_cache()

                # Make sure project_id is set correctly on the product
                if res.apartment_id.project_id and res.project_id.id != res.apartment_id.project_id.id:
                    res.project_id = res.apartment_id.project_id.id
            except Exception as e:
                _logger.error("Error updating apartment after product creation: %s", str(e))
        # Handle store naming
        elif res.is_store and res.building_id:
            try:
                # Only generate a name if the user hasn't entered one or if it's a default name
                default_names = ['New Store', 'New Product', f"Store {int(time.time()) % 10000}"]
                if res.building_id and res.floor is not None and (not res.name or res.name in default_names):
                    # Count existing stores on this floor in this building
                    floor = res.floor or 0
                    existing_count = self.env['product.template'].search_count([
                        ('building_id', '=', res.building_id.id),
                        ('floor', '=', floor),
                        ('is_store', '=', True)
                    ])

                    # Generate store number
                    building_prefix = res.building_id.code[0].upper() if res.building_id.code else 'S'
                    store_number = f"{building_prefix}{floor:02d}{existing_count:02d}"  # Use existing_count without +1

                    # Set the name to "Store" followed by the number only if user hasn't entered a custom name
                    suggested_name = f"Store {store_number}"
                    res.name = suggested_name
                    res.default_code = f"STR-{store_number}"
                    _logger.info("Generated store name %s for new store", suggested_name)
                else:
                    _logger.info("Keeping user-entered store name: %s", res.name)

                # Update the stock quantity
                _logger.info("Setting initial quantity for new store %s", res.name)
            except Exception as e:
                _logger.error("Error updating store after product creation: %s", str(e))

        # Handle équipement naming
        elif res.is_equipement and res.building_id:
            try:
                # Only generate a name if the user hasn't entered one or if it's a default name
                default_names = ['New Équipement', 'New Product', f"Équipement {int(time.time()) % 10000}"]
                if res.building_id and res.floor is not None and (not res.name or res.name in default_names):
                    # Count existing équipements on this floor in this building
                    floor = res.floor or 0
                    existing_count = self.env['product.template'].search_count([
                        ('building_id', '=', res.building_id.id),
                        ('floor', '=', floor),
                        ('is_equipement', '=', True)
                    ])

                    # Generate équipement number
                    building_prefix = res.building_id.code[0].upper() if res.building_id.code else 'E'
                    equipement_number = f"{building_prefix}{floor:02d}{existing_count:02d}"  # Use existing_count without +1

                    # Set the name to "Équipement" followed by the number only if user hasn't entered a custom name
                    suggested_name = f"Équipement {equipement_number}"
                    res.name = suggested_name
                    res.default_code = f"EQP-{equipement_number}"
                    _logger.info("Generated équipement name %s for new équipement", suggested_name)
                else:
                    _logger.info("Keeping user-entered équipement name: %s", res.name)

                # Update the stock quantity
                _logger.info("Setting initial quantity for new équipement %s", res.name)
            except Exception as e:
                _logger.error("Error updating équipement after product creation: %s", str(e))

        # Update stock quantity for apartments, stores, and équipements
        if res.is_apartment or res.is_store or res.is_equipement:
            try:
                res._update_stock_quantity()
            except Exception as e:
                _logger.error("Error updating initial stock quantity: %s", str(e))

        return res

    def write(self, vals):
        """Override write to sync changes with apartment"""
        # Check if we're being called from apartment update or delete to avoid infinite recursion
        if self.env.context.get('from_apartment_update') or self.env.context.get('from_apartment_delete'):
            # Just perform the write operation without additional quantity updates
            # The apartment module will handle quantity updates separately
            return super(ProductTemplate, self).write(vals)

        # Store original values for comparison
        original_vals = {}
        for product in self:
            if product.is_apartment or product.is_store:
                original_vals[product.id] = {
                    'building_id': product.building_id.id if product.building_id else False,
                    'project_id': product.project_id.id if product.project_id else False,
                    'apartment_id': product.apartment_id.id if product.apartment_id else False,
                    'apartment_state': product.apartment_state,
                }

        # Handle project_id and building_id relationship
        if 'project_id' in vals and vals['project_id']:
            # If project is changing and building belongs to a different project, reset building
            for product in self:
                if product.building_id and product.building_id.project_id.id != vals['project_id']:
                    # Try to find a building for the new project
                    building = self.env['real.estate.building'].search([
                        ('project_id', '=', vals['project_id'])
                    ], limit=1)

                    if building:
                        vals['building_id'] = building.id
                        _logger.info("Auto-selected building %s for new project %s", building.name, vals['project_id'])
                    else:
                        # Don't create a default building, just log a message
                        _logger.info("No building found for project ID %s. Please select a building.", vals['project_id'])

        # Check if we're setting is_apartment to True and need to create an apartment
        if vals.get('is_apartment'):
            for product in self:
                if not product.is_apartment or not product.apartment_id:
                    # Make sure we have a name
                    name = vals.get('name', product.name or f"New Apartment {int(time.time()) % 10000}")

                    # Make sure we have a price
                    price = vals.get('list_price', product.list_price or 0.0)

                    # Make sure we have a building_id
                    building_id = vals.get('building_id', product.building_id.id if product.building_id else False)

                    # If we have project_id but no building_id, try to find or create a building
                    if not building_id:
                        project_id = vals.get('project_id', product.project_id.id if product.project_id else False)
                        if project_id:
                            # Try to find a building for this project
                            building = self.env['real.estate.building'].search([
                                ('project_id', '=', project_id)
                            ], limit=1)

                            if building:
                                building_id = building.id
                                vals['building_id'] = building_id
                                _logger.info("Found building %s for project %s", building.name, project_id)
                            else:
                                # Don't create a default building, just log a message
                                _logger.info("No building found for project ID %s. Please select a building.", project_id)

                    # If we don't have a building_id, we can't create an apartment
                    if not building_id:
                        _logger.warning("Cannot create apartment without building_id. Please select a building first.")
                        # Skip apartment creation
                        continue

                    # If we now have a building_id, create the apartment
                    if building_id:
                        # Prepare values for creating a new apartment
                        apartment_vals = {
                            'name': name,
                            'code': vals.get('default_code', product.default_code) or self.env['ir.sequence'].next_by_code('real.estate.apartment') or f"APT-{int(time.time()) % 10000}",
                            'building_id': building_id,
                            'floor': vals.get('floor', product.floor or 0),
                            'price': price,
                            'area': vals.get('area', product.area or 0.0),
                            'rooms': vals.get('rooms', product.rooms or 1),
                            'bathrooms': vals.get('bathrooms', product.bathrooms or 1),
                            'description': vals.get('description', product.description or ''),
                            'state': vals.get('apartment_state', product.apartment_state or 'disponible'),
                        }

                        # Prepare apartment values using the method to ensure consistency
                        apartment_vals = self._prepare_apartment_vals({
                            'name': name,
                            'default_code': vals.get('default_code', product.default_code),
                            'building_id': building_id,
                            'floor': vals.get('floor', product.floor or 0),
                            'list_price': price,
                            'area': vals.get('area', product.area or 0.0),
                            'rooms': vals.get('rooms', product.rooms or 1),
                            'bathrooms': vals.get('bathrooms', product.bathrooms or 1),
                            'description': vals.get('description', product.description or ''),
                            'apartment_state': vals.get('apartment_state', product.apartment_state or 'disponible'),
                        })

                        if apartment_vals:
                            try:
                                # Check if we're using an existing apartment
                                if 'existing_id' in apartment_vals:
                                    # Use the existing apartment instead of creating a new one
                                    vals['apartment_id'] = apartment_vals['existing_id']
                                    _logger.info("Using existing apartment with ID %s during write", apartment_vals['existing_id'])
                                else:
                                    # Create a new apartment with context to prevent circular reference
                                    apartment = self.env['real.estate.apartment'].with_context(from_product_create=True).create(apartment_vals)
                                    vals['apartment_id'] = apartment.id
                                    _logger.info("Created apartment %s from product during write", apartment.name)
                            except Exception as e:
                                _logger.error("Error creating apartment from product during write: %s", str(e))
                    else:
                        _logger.warning("Cannot create apartment without building_id")

        # Call super to perform the actual write
        res = super(ProductTemplate, self).write(vals)

        # After write, update apartments if needed and ensure quantity is correct
        for product in self:
            if product.is_apartment and product.apartment_id:
                try:
                    # Update stock quantity if apartment state has changed
                    if 'apartment_state' in vals:
                        _logger.info("Apartment state changed to %s for %s, updating stock quantity",
                                    product.apartment_state, product.name)
                        product._update_stock_quantity()

                    # Check what has changed
                    update_vals = {}

                    # If building has changed, update apartment
                    if 'building_id' in vals and product.building_id and product.apartment_id.building_id.id != product.building_id.id:
                        update_vals['building_id'] = product.building_id.id
                        _logger.info("Updating apartment building to %s", product.building_id.name)

                    # Get other field updates
                    field_mapping = {
                        'name': 'name',
                        'default_code': 'code',
                        'list_price': 'price',
                        'floor': 'floor',
                        'area': 'area',
                        'rooms': 'rooms',
                        'bathrooms': 'bathrooms',
                        'description': 'description',
                        'apartment_state': 'state',
                    }

                    for product_field, apartment_field in field_mapping.items():
                        if product_field in vals:
                            update_vals[apartment_field] = vals[product_field]

                    if update_vals:
                        product.apartment_id.write(update_vals)
                        _logger.info("Updated apartment %s from product with values: %s",
                                    product.apartment_id.name, update_vals)

                        # Invalidate cache to ensure related fields are updated
                        product.apartment_id.invalidate_cache()
                        product.invalidate_cache()

                    # Make sure project_id is set correctly on the product
                    if product.apartment_id.project_id and product.project_id.id != product.apartment_id.project_id.id:
                        product.project_id = product.apartment_id.project_id.id
                except Exception as e:
                    _logger.error("Error updating apartment from product: %s", str(e))

            # Store handling
            elif product.is_store:
                try:
                    # Update stock quantity if store state has changed
                    if 'apartment_state' in vals or product.id in original_vals:
                        _logger.info("Store state is %s for %s, updating stock quantity",
                                    product.apartment_state, product.name)
                        product._update_stock_quantity()
                except Exception as e:
                    _logger.error("Error updating store: %s", str(e))

        # Quantity management is now handled by Odoo's standard inventory management

        return res

    def _prepare_apartment_vals(self, vals):
        """Prepare values for creating a new apartment"""
        # Check if we have a building_id - this is required for apartments
        if not vals.get('building_id'):
            _logger.warning("Cannot create apartment without building_id")
            return False

        # Get the building for reference
        building = False
        try:
            building = self.env['real.estate.building'].browse(vals.get('building_id'))
            if not building.exists():
                _logger.error("Building with ID %s does not exist", vals.get('building_id'))
                return False
        except Exception as e:
            _logger.error("Error verifying building: %s", str(e))
            return False

        # Generate apartment number based on existing apartments in this building
        floor = vals.get('floor', 0)

        # Count existing apartments on this floor in this building
        existing_count = self.env['real.estate.apartment'].search_count([
            ('building_id', '=', building.id),
            ('floor', '=', floor)
        ])

        # Only generate a name if the user hasn't entered one or if it's a default name
        default_names = ['New Apartment', 'New Product', f"Apartment {int(time.time()) % 10000}"]
        if not vals.get('name') or vals.get('name') in default_names:
            # Generate apartment number (e.g., A101 for building A, floor 1, apt 01)
            building_prefix = building.code[0].upper() if building.code else 'A'
            apt_number = f"{building_prefix}{floor:02d}{existing_count+1:02d}"

            # Set the name to "Apartment" followed by the number only if user hasn't entered a custom name
            vals['name'] = f"Apartment {apt_number}"
            _logger.info("Generated apartment name %s in _prepare_apartment_vals", vals['name'])
        else:
            _logger.info("Keeping user-entered apartment name: %s", vals.get('name'))

        # Generate a code if not provided
        if not vals.get('default_code'):
            # Only use apt_number if it was generated above
            if not vals.get('name') or vals.get('name') in default_names:
                building_prefix = building.code[0].upper() if building.code else 'A'
                apt_number = f"{building_prefix}{floor:02d}{existing_count+1:02d}"
                vals['default_code'] = apt_number
            else:
                # Generate a unique code based on the name and type
                if vals.get('is_apartment', False):
                    vals['default_code'] = f"APT-{int(time.time()) % 10000}"
                elif vals.get('is_store', False):
                    vals['default_code'] = f"STR-{int(time.time()) % 10000}"
                else:
                    vals['default_code'] = f"APT-{int(time.time()) % 10000}"

        # Make sure we have a floor
        if not vals.get('floor') and vals.get('floor') != 0:
            vals['floor'] = 1

        # Make sure we have a price
        if not vals.get('list_price'):
            vals['list_price'] = 0.0

        # Make sure we have area
        if not vals.get('area'):
            vals['area'] = 0.0

        # Check if an apartment with the same building and code already exists
        # Only check if apt_number was generated
        if 'default_code' in vals and vals['default_code']:
            existing_apartment = self.env['real.estate.apartment'].search([
                ('building_id', '=', building.id),
                ('code', '=', vals['default_code'])
            ], limit=1)
        else:
            existing_apartment = self.env['real.estate.apartment'].browse()

        if existing_apartment:
            _logger.warning(
                "An apartment with code %s already exists in building %s on floor %s. "
                "Using existing apartment instead of creating a new one.",
                vals.get('default_code', ''), building.name, floor
            )
            # Return the existing apartment's ID to link to it instead of creating a new one
            return {
                'name': existing_apartment.name,
                'code': existing_apartment.code,
                'building_id': existing_apartment.building_id.id,
                'floor': existing_apartment.floor,
                'price': existing_apartment.price,
                'area': existing_apartment.area,
                'rooms': existing_apartment.rooms,
                'bathrooms': existing_apartment.bathrooms,
                'description': existing_apartment.description,
                'state': existing_apartment.state,
                'existing_id': existing_apartment.id  # Special field to indicate this is an existing apartment
            }

        # Prepare apartment values
        apartment_vals = {
            'name': vals.get('name', ''),
            'code': vals.get('default_code', ''),
            'building_id': vals.get('building_id'),
            'floor': vals.get('floor', 0),
            'price': vals.get('list_price', 0.0),
            'area': vals.get('area', 0.0),
            'rooms': vals.get('rooms', 1),
            'bathrooms': vals.get('bathrooms', 1),
            'description': vals.get('description', ''),
            'state': vals.get('apartment_state', 'disponible'),
        }

        # Log the values for debugging
        _logger.info("Prepared apartment values: %s", apartment_vals)

        return apartment_vals

    def _update_stock_quantity(self):
        """Update the stock quantity based on apartment/store/équipement state"""
        for product in self:
            if not (product.is_apartment or product.is_store):
                continue

            # Get the product variant
            product_variant = product.product_variant_id
            if not product_variant:
                _logger.error("No product variant found for %s", product.name)
                continue

            # Get the stock location - use the default stock location
            stock_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
            if not stock_location:
                # Fallback to searching for a stock location
                stock_location = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)

            if not stock_location:
                _logger.error("No internal stock location found for company %s", self.env.company.name)
                continue

            # Determine the quantity based on state and product type
            quantity = 0.0
            if product.apartment_state == 'disponible':
                if product.is_store and product.area:
                    # For stores, use surface area as inventory quantity
                    quantity = product.area
                else:
                    # For apartments and équipements, use quantity 1
                    quantity = 1.0

            _logger.info("Setting quantity for %s to %s (state: %s)",
                        product.name, quantity, product.apartment_state)

            try:
                # Create an inventory adjustment
                inventory_adjustment = self.env['stock.quant'].with_context(inventory_mode=True).create({
                    'product_id': product_variant.id,
                    'location_id': stock_location.id,
                    'inventory_quantity': quantity,
                })

                # Apply the inventory adjustment
                inventory_adjustment.action_apply_inventory()

                # Invalidate the cache to ensure qty_available is updated
                product.invalidate_cache(['qty_available'])
                product_variant.invalidate_cache(['qty_available'])

                # Log success
                _logger.info("Successfully updated stock quantity for %s to %s", product.name, quantity)

                # Force a refresh of the product
                self.env.cr.commit()

            except Exception as e:
                _logger.error("Error updating stock quantity for %s: %s", product.name, str(e))

    def _prepare_apartment_update_vals(self, vals):
        """Prepare values for updating an existing apartment"""
        apartment_vals = {}

        # Map product fields to apartment fields
        field_mapping = {
            'name': 'name',
            'default_code': 'code',
            'list_price': 'price',
            'floor': 'floor',
            'area': 'area',
            'rooms': 'rooms',
            'bathrooms': 'bathrooms',
            'description': 'description',
            'apartment_state': 'state',
            'building_id': 'building_id',
        }

        for product_field, apartment_field in field_mapping.items():
            if product_field in vals:
                apartment_vals[apartment_field] = vals[product_field]

        return apartment_vals

    def _get_or_create_project_category(self, project):
        """Get or create product category for project"""
        if not project:
            return False

        category = self.env['product.category'].search([
            ('name', '=', project.name),
        ], limit=1)

        if not category:
            category = self.env['product.category'].create({
                'name': project.name,
            })

        return category

    def action_create_reservation(self):
        """Create a new reservation (quotation) for this property (apartment, store, or équipement)"""
        self.ensure_one()

        if not (self.is_apartment or self.is_store or self.is_equipement):
            raise UserError(_("This action is only available for real estate properties (apartments, stores, or équipements)."))

        # Check if property is available
        if self.apartment_state != 'disponible':
            raise UserError(_("Only disponible properties can be reserved."))

        # For apartments, check if we have an apartment_id
        if self.is_apartment and not self.apartment_id:
            # Try to create the apartment if it doesn't exist
            try:
                _logger.info("Apartment ID not found. Attempting to create a new apartment record.")

                # Prepare apartment values
                apartment_vals = {
                    'name': self.name,
                    'code': self.default_code or f"APT-{int(time.time()) % 10000}",
                    'building_id': self.building_id.id if self.building_id else False,
                    'floor': self.floor or 0,
                    'price': self.list_price or 0.0,
                    'area': self.area or 0.0,
                    'rooms': self.rooms or 1,
                    'bathrooms': self.bathrooms or 1,
                    'description': self.description or '',
                    'state': self.apartment_state or 'disponible',
                }

                # Check if we have a building_id - this is required for apartments
                if not apartment_vals.get('building_id'):
                    raise UserError(_("Cannot create apartment without building. Please select a building first."))

                # Create a new apartment with context to prevent circular reference
                apartment = self.env['real.estate.apartment'].with_context(from_product_create=True).create(apartment_vals)

                # Link the apartment to this product
                self.apartment_id = apartment.id
                _logger.info("Created and linked apartment %s with ID %s", apartment.name, apartment.id)

                # Force a cache invalidation to ensure the link is saved
                self.invalidate_cache()

                # Refresh the record
                self = self.browse(self.id)

                if not self.apartment_id:
                    raise UserError(_("Failed to link the apartment. Please try again or contact your administrator."))
            except Exception as e:
                _logger.error("Error creating apartment: %s", str(e))
                raise UserError(_("Failed to create apartment: %s") % str(e))

        # Create a new quotation with this apartment/store/équipement
        SaleOrder = self.env['sale.order']
        
        # Clear any type from context that might interfere with partner creation
        clean_context = dict(self.env.context)
        if 'type' in clean_context:
            del clean_context['type']
        
        SaleOrder = SaleOrder.with_context(clean_context)

        # Generate a detailed description for the property
        if self.is_apartment:
            # For apartments, use the apartment_id data
            apartment = self.apartment_id
            project_name = apartment.project_id.name if apartment.project_id else "N/A"
            building_name = apartment.building_id.name if apartment.building_id else "N/A"
            floor = apartment.floor if apartment.floor is not None else "N/A"
            area = apartment.area if apartment.area else "N/A"
            rooms = apartment.rooms if apartment.rooms else "N/A"
            bathrooms = apartment.bathrooms if apartment.bathrooms else "N/A"

            property_description = f"""
Projet: {project_name}
Bâtiment: {building_name}
Appartement: {apartment.name}
Étage: {floor}
Surface: {area} m²
Pièces: {rooms}
Salles de bain: {bathrooms}
"""
        else:
            # For stores and équipements, use the product data directly
            project_name = self.project_id.name if self.project_id else "N/A"
            building_name = self.building_id.name if self.building_id else "N/A"
            floor = self.floor if self.floor is not None else "N/A"
            area = self.area if self.area else "N/A"
            
            if self.is_store:
                property_description = f"""
Projet: {project_name}
Bâtiment: {building_name}
Magasin: {self.name}
Étage: {floor}
Surface: {area} m²
"""
            elif self.is_equipement:
                property_description = f"""
Projet: {project_name}
Bâtiment: {building_name}
Équipement: {self.name}
Étage: {floor}
Surface: {area} m²
"""

        # Prepare the order values - without partner_id
        order_line_vals = {
            'product_id': self.product_variant_id.id,
            'building_id': self.building_id.id if self.building_id else False,
            'product_uom_qty': self.area if self.is_store and self.area else 1,
            'price_unit': self.list_price,
            'name': property_description,
        }

        # Add apartment_id only for apartments
        if self.is_apartment:
            order_line_vals['apartment_id'] = self.apartment_id.id

        order_vals = {
            'is_real_estate': True,
            'project_id': self.project_id.id if self.project_id else False,
            'order_line': [(0, 0, order_line_vals)],
            'state': 'draft',  # Ensure it's a draft
        }

        # Create the quotation with a clean context
        new_order = SaleOrder.create(order_vals)

        # Log the creation - using separate variables to avoid context leakage
        property_type = 'apartment' if self.is_apartment else ('store' if self.is_store else 'équipement')
        _logger.info("Created new reservation %s for %s %s", new_order.name, property_type, self.name)

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

    def action_cancel_reservation(self):
        """Cancel the reservation and return the apartment/store/équipement to disponible state"""
        self.ensure_one()
        
        if self.apartment_state != 'prereserved':
            raise UserError(_("Cannot cancel reservation: property is not in préréservé state"))
            
        # Find any related sale order lines for this property
        sale_lines = self.env['sale.order.line'].search([
            ('product_id.product_tmpl_id', '=', self.id),
            ('order_id.state', 'in', ['draft', 'sent', 'sale'])
        ])
        
        # Check if there are active orders that need to be handled
        if sale_lines:
            confirmed_orders = sale_lines.filtered(lambda l: l.order_id.state == 'sale')
            if confirmed_orders:
                # If there are confirmed orders, ask user for confirmation
                order_names = ', '.join(confirmed_orders.mapped('order_id.name'))
                raise UserError(_(
                    "Cannot cancel reservation: there are confirmed sale orders (%s) for this property. "
                    "Please cancel the sale orders first."
                ) % order_names)
            
            # Cancel any draft or sent orders
            draft_orders = sale_lines.filtered(lambda l: l.order_id.state in ['draft', 'sent']).mapped('order_id')
            for order in draft_orders:
                order.action_cancel()
                _logger.info("Cancelled sale order %s when canceling reservation for %s", order.name, self.name)
            
        # Update apartment/store/équipement status
        self.write({
            'apartment_state': 'disponible',
            'is_locked': False,
            'locked_by_order_id': False,
            'lock_date': False
        })
        
        # If linked to an apartment record, update it too
        if self.apartment_id:
            self.apartment_id.write({
                'state': 'disponible',
                'is_locked': False,
                'locked_by_order_id': False,
                'lock_date': False
            })
            
        # Log the action in the chatter
        property_type = "apartment" if self.is_apartment else "store"
        message = _("Reservation cancelled: %s returned to disponible state") % property_type
        self.message_post(body=message, message_type='comment')
        
        # Show success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reservation Cancelled'),
                'message': _('The reservation has been cancelled and the %s is now disponible.') % property_type,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_cancel_sold_property(self):
        """Cancel a sold property and return it to disponible state, handling invoices"""
        self.ensure_one()
        
        if self.apartment_state != 'sold':
            raise UserError(_("Can only cancel sold properties. Current state: %s") % dict(self._fields['apartment_state'].selection)[self.apartment_state])
        
        property_type = "apartment" if self.is_apartment else ("store" if self.is_store else "équipement")
        
        # Find all related sale order lines for this property
        sale_lines = self.env['sale.order.line'].search([
            ('product_id.product_tmpl_id', '=', self.id),
            ('order_id.state', 'in', ['sale', 'done'])
        ])
        
        if not sale_lines:
            # No sale orders found, just change state
            self._reset_property_to_disponible(property_type)
            return self._show_cancel_success_notification(property_type)
        
        # Get all related sale orders
        sale_orders = sale_lines.mapped('order_id')
        confirmed_orders = sale_orders.filtered(lambda o: o.state == 'sale')
        
        if confirmed_orders:
            # Find and handle related invoices
            invoices_to_handle = []
            for order in confirmed_orders:
                # Get all invoices for this order
                order_invoices = order.invoice_ids.filtered(lambda inv: inv.state in ['posted', 'paid'])
                if order_invoices:
                    invoices_to_handle.extend(order_invoices)
            
            # Ask for confirmation if there are posted invoices
            if invoices_to_handle:
                invoice_names = ', '.join([inv.name for inv in invoices_to_handle])
                # For now, we'll provide a warning but still allow the cancellation
                # In a production environment, you might want to require special permissions
                _logger.warning(
                    "Cancelling sold %s %s with posted invoices: %s. "
                    "Consider creating credit notes if accounting reconciliation is needed.",
                    property_type, self.name, invoice_names
                )
            
            # Cancel the sale orders (this will also update the property state)
            try:
                for order in confirmed_orders:
                    order.action_cancel()
                    _logger.info("Cancelled sale order %s when canceling sold %s %s", 
                               order.name, property_type, self.name)
            except Exception as e:
                _logger.error("Error cancelling sale order: %s", str(e))
                # If we can't cancel the orders, still proceed with state change
                # as the user specifically requested to cancel the sold property
                pass
        
        # Ensure the property is set to disponible
        self._reset_property_to_disponible(property_type)
        
        # Log the action in the chatter
        message = _("Sold %s cancelled: returned to disponible state") % property_type
        if invoices_to_handle:
            message += _(" (Warning: Related invoices exist: %s)") % ', '.join([inv.name for inv in invoices_to_handle])
        self.message_post(body=message, message_type='comment')
        
        return self._show_cancel_success_notification(property_type, sold=True)
    
    def _reset_property_to_disponible(self, property_type):
        """Reset property to disponible state"""
        # Update property status
        self.write({
            'apartment_state': 'disponible',
            'is_locked': False,
            'locked_by_order_id': False,
            'lock_date': False
        })
        
        # If linked to an apartment record, update it too
        if self.apartment_id:
            self.apartment_id.write({
                'state': 'disponible',
                'is_locked': False,
                'locked_by_order_id': False,
                'lock_date': False
            })
        
        _logger.info("Reset %s %s to disponible state", property_type, self.name)
    
    def _show_cancel_success_notification(self, property_type, sold=False):
        """Show success notification for cancellation"""
        title = _('Sold Property Cancelled') if sold else _('Reservation Cancelled')
        message_type = 'sold property' if sold else 'reservation'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': _('The %s has been cancelled and the %s is now disponible.') % (message_type, property_type),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_confirm_reservation(self):
        """Confirm the reservation by opening the related quotation"""
        self.ensure_one()
        
        if self.apartment_state != 'prereserved':
            raise UserError(_("Can only confirm reservations for préréservé properties"))
            
        # Find the active sale order for this property
        sale_lines = self.env['sale.order.line'].search([
            ('product_id.product_tmpl_id', '=', self.id),
            ('order_id.state', 'in', ['draft', 'sent'])
        ])
        
        if not sale_lines:
            raise UserError(_("No active quotation found for this property"))
            
        # Get the most recent quotation
        active_order = sale_lines.mapped('order_id').sorted('create_date', reverse=True)[0]
        
        # Return an action to open the quotation
        return {
            'name': _('Confirm Reservation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': active_order.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
                'show_confirm_message': True
            }
        }

    def action_view_reservation_document(self):
        """View the reservation document (invoice) for sold properties"""
        self.ensure_one()
        
        if self.apartment_state != 'sold':
            raise UserError(_("Can only view reservation documents for sold properties"))
            
        # Find the confirmed sale order for this property
        sale_lines = self.env['sale.order.line'].search([
            ('product_id.product_tmpl_id', '=', self.id),
            ('order_id.state', 'in', ['sale', 'done'])
        ])
        
        if not sale_lines:
            raise UserError(_("No confirmed sale order found for this property"))
            
        # Get the most recent confirmed order
        confirmed_order = sale_lines.mapped('order_id').sorted('create_date', reverse=True)[0]
        
        # Look for invoices related to this order
        invoices = self.env['account.move'].search([
            ('invoice_origin', '=', confirmed_order.name),
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel')
        ])
        
        if invoices:
            # If there are multiple invoices, get the most recent one
            invoice = invoices.sorted('create_date', reverse=True)[0]
            
            return {
                'name': _('Reservation Document'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': invoice.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'context': {'form_view_initial_mode': 'readonly'}
            }
        else:
            # If no invoice exists, show the confirmed sale order
            return {
                'name': _('Reservation Document'),
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': confirmed_order.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'context': {
                    'form_view_initial_mode': 'readonly',
                    'hide_edit_button': True
                }
            }

    @api.model
    def action_update_all_quantities(self):
        """Update quantity for all apartments and stores"""
        # Find all apartment and store products
        products = self.search([
            '|',
            ('is_apartment', '=', True),
            ('is_store', '=', True)
        ])

        _logger.info("Updating quantities for %s products (apartments and stores)", len(products))

        # Update quantities for all products
        for product in products:
            try:
                product._update_stock_quantity()
            except Exception as e:
                _logger.error("Error updating quantity for %s: %s", product.name, str(e))

        _logger.info("Finished updating quantities for all products")
        return True

    def action_open_quants(self):
        """Open the stock quants view for this property (apartment or store)"""
        self.ensure_one()

        if not (self.is_apartment or self.is_store):
            raise UserError(_("This action is only available for real estate properties (apartments or stores)."))

        # Get the product variant
        product_variant = self.product_variant_ids[0] if self.product_variant_ids else False
        if not product_variant:
            property_type = "apartment" if self.is_apartment else "store"
            raise UserError(_("No product variant found for this %s.") % property_type)

        # Open the stock quants view
        property_type = "Apartment" if self.is_apartment else "Store"
        return {
            'name': _('%s Stock On Hand') % property_type,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('product_id', '=', product_variant.id), ('location_id.usage', '=', 'internal')],
            'context': {
                'search_default_internal_loc': 1,
                'search_default_productgroup': 1,
            }
        }

    # Quantity management is now handled by Odoo's standard inventory management

    def _get_or_create_building_category(self, building):
        """Get or create product category for building"""
        if not building:
            return False

        # Get parent category (project)
        parent_category = self._get_or_create_project_category(building.project_id)

        category = self.env['product.category'].search([
            ('name', '=', building.name),
            ('parent_id', '=', parent_category.id if parent_category else False),
        ], limit=1)

        if not category and parent_category:
            category = self.env['product.category'].create({
                'name': building.name,
                'parent_id': parent_category.id,
            })

        return category

    @api.constrains('is_apartment', 'is_store', 'is_equipement')
    def _check_apartment_store_exclusivity(self):
        """Ensure a product can't be both an apartment, store, and équipement"""
        for product in self:
            if sum(bool(x) for x in [product.is_apartment, product.is_store, product.is_equipement]) > 1:
                raise UserError(_("A product can only be one type: apartment, store, or équipement. Please select only one option."))

    @api.constrains('is_store', 'building_id')
    def _check_building_required_store(self):
        """Ensure building is set for stores"""
        for product in self:
            if product.is_store and not product.building_id:
                raise UserError(_("Building is required for stores. Please select a building."))

    @api.constrains('is_equipement', 'building_id')
    def _check_building_required_equipement(self):
        """Ensure building is set for équipement"""
        for product in self:
            if product.is_equipement and not product.building_id:
                raise UserError(_("Building is required for équipement. Please select a building."))

    @api.constrains('is_store', 'area')
    def _check_store_area_valid(self):
        """Ensure area is greater than 0 for stores"""
        for product in self:
            if product.is_store and (not product.area or product.area <= 0):
                raise UserError(_("Area must be strictly greater than 0 m² for stores. Please enter a valid area (minimum 1 m²)."))

    @api.onchange('sale_ok')
    def _onchange_sale_ok(self):
        """When sale_ok changes, update apartment_state accordingly"""
        if hasattr(self, 'is_apartment') and hasattr(self, 'is_store') and hasattr(self, 'is_equipement'):
            if (self.is_apartment or self.is_store or self.is_equipement):
                if not self.sale_ok:
                    # Set to blocker when sale_ok is unchecked
                    self.apartment_state = 'blocker'
                elif self.apartment_state == 'blocker':
                    # Return to disponible when sale_ok is checked again (from blocker state)
                    self.apartment_state = 'disponible'