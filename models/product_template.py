from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import time

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Real Estate specific fields
    is_apartment = fields.Boolean(string='Is Apartment', default=False)
    apartment_id = fields.Many2one('real.estate.apartment', string='Apartment')

    # Direct fields for apartment properties
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

    # State for apartments
    apartment_state = fields.Selection([
        ('available', 'Available'),
        ('in_progress', 'Réservation en cours'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
    ], string='Apartment Status', default='available')

    # Locking mechanism fields
    is_locked = fields.Boolean(string='Locked', related='apartment_id.is_locked', readonly=True,
                              help="Indicates if the apartment is locked for a quotation")
    locked_by_order_id = fields.Many2one('sale.order', string='Locked By Order',
                                       related='apartment_id.locked_by_order_id', readonly=True,
                                       help="The quotation that has locked this apartment")
    lock_date = fields.Datetime(string='Lock Date', related='apartment_id.lock_date', readonly=True,
                              help="Date and time when the apartment was locked")

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

            # Clear taxes for apartments
            self.taxes_id = False

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

    @api.onchange('apartment_state')
    def _onchange_apartment_state(self):
        """When apartment state changes, schedule inventory update after save"""
        if self.is_apartment:
            # Log the state change
            _logger.info("Apartment state changed to %s for apartment %s", self.apartment_state, self.name)

            # Note: We can't update the quantity directly in an onchange method
            # because the changes won't persist. The quantity will be updated
            # when the record is saved through the write method.

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

            # Note: We'll set the quantity after creation using _force_inventory_quantity
            # Don't set qty_available directly as it won't affect inventory
            _logger.info("Will set inventory quantity after product creation")

            # Clear taxes for apartments
            vals['taxes_id'] = [(5, 0, 0)]  # Clear all taxes

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
                    res.default_code = apt_number
                    _logger.info("Generated apartment name %s for new apartment", suggested_name)
                else:
                    _logger.info("Keeping user-entered apartment name: %s", res.name)

                # Set initial inventory quantity based on apartment state
                _logger.info("Setting initial inventory quantity for new apartment %s with state %s",
                            res.name, res.apartment_state)

                # IMPROVED: Force immediate quantity update with stronger cache invalidation
                self._force_inventory_quantity(res)

                # Verify the quantity was set correctly
                res.invalidate_cache(['qty_available'])
                self.env.clear_cache()

                # Refresh the product to get the latest quantity
                res = self.browse(res.id)

                _logger.info("Initial quantity for %s: %s", res.name, res.qty_available)

                # If quantity is still not set correctly, try again with direct method
                if res.apartment_state == 'available' and res.qty_available < 1.0:
                    _logger.warning("Initial quantity not set correctly. Trying direct method.")

                    # Get the product variant and location
                    variant = res.product_variant_ids[0]
                    warehouse = self.env['stock.warehouse'].search([], limit=1)
                    location = warehouse.lot_stock_id

                    # Use direct method
                    self._force_quantity_direct(variant.id, location.id, 1.0)

                    # Invalidate cache again
                    res.invalidate_cache(['qty_available'])
                    self.env.clear_cache()

                    # Refresh the product again
                    res = self.browse(res.id)
                    _logger.info("After direct update, initial quantity for %s: %s", res.name, res.qty_available)

                # The post-commit hook will ensure the quantity is set correctly
                # even if there are cache issues

                # Schedule a post-commit update to ensure quantity is set correctly
                self.env.cr.after('commit', lambda: self._post_commit_update_quantity(res.id))

                _logger.info("Scheduled post-commit job to ensure quantity is set correctly")

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
            if product.is_apartment:
                original_vals[product.id] = {
                    'building_id': product.building_id.id if product.building_id else False,
                    'project_id': product.project_id.id if product.project_id else False,
                    'apartment_id': product.apartment_id.id if product.apartment_id else False,
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
                            'state': vals.get('apartment_state', product.apartment_state or 'available'),
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
                            'apartment_state': vals.get('apartment_state', product.apartment_state or 'available'),
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

        # After write, update apartments if needed
        for product in self:
            if product.is_apartment and product.apartment_id:
                try:
                    # Update inventory quantity if apartment state changed
                    if 'apartment_state' in vals:
                        _logger.info("Apartment state changed to %s for %s, updating inventory quantity",
                                    product.apartment_state, product.name)

                        # Use our simplified method to set the quantity
                        # It will determine the correct quantity based on apartment_state
                        self._force_inventory_quantity(product)

                    # Check if we need to force quantity to a specific value
                    force_qty = self.env.context.get('force_qty_available')
                    if force_qty is not None:
                        _logger.info("Forcing quantity to %s for apartment %s after write",
                                    force_qty, product.name)
                        self._force_inventory_quantity(product, force_qty)

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
                # Generate a unique code based on the name
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
            'state': vals.get('apartment_state', 'available'),
        }

        # Log the values for debugging
        _logger.info("Prepared apartment values: %s", apartment_vals)

        return apartment_vals

    def _force_inventory_quantity(self, product, quantity=None):
        """
        Force the inventory quantity for a product.
        This is the single source of truth for setting quantities.

        Args:
            product: The product to update
            quantity: The quantity to set. If None, will be determined based on apartment_state

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # If quantity is not provided, determine it based on apartment state
            if quantity is None:
                if product.apartment_state == 'available':
                    quantity = 1.0
                else:
                    quantity = 0.0

            # For available apartments, always force quantity to 1
            if product.is_apartment and product.apartment_state == 'available':
                quantity = 1.0

            # Get the product variant
            if not product.product_variant_ids:
                _logger.error("No product variant found for apartment %s", product.name)
                return False

            variant = product.product_variant_ids[0]

            # Log current quantity before changes
            _logger.info("Setting quantity for %s to %s (current: %s, state: %s)",
                        product.name, quantity, product.qty_available, product.apartment_state)

            # Get the main stock location
            warehouse = self.env['stock.warehouse'].search([], limit=1)
            if not warehouse:
                # Create a default warehouse if none exists
                warehouse = self.env['stock.warehouse'].create({
                    'name': 'Default Warehouse',
                    'code': 'DEF',
                })

            location = warehouse.lot_stock_id

            # Use the standard Odoo method to update quantity
            # This is more reliable than direct SQL operations
            StockQuant = self.env['stock.quant']

            # First, remove existing quants to avoid quantity inconsistencies
            quants = StockQuant.search([
                ('product_id', '=', variant.id),
                ('location_id', '=', location.id)
            ])

            if quants:
                quants.sudo().unlink()
                _logger.info("Deleted existing quants for product %s", product.name)

            # Create a new quant with the correct quantity
            if quantity > 0:
                StockQuant.sudo().create({
                    'product_id': variant.id,
                    'location_id': location.id,
                    'quantity': quantity,
                    'company_id': self.env.company.id,
                    'in_date': fields.Datetime.now(),
                })
                _logger.info("Created new quant for product %s with quantity %s", product.name, quantity)

            # Force a complete cache invalidation
            self.env.cache.invalidate()
            product.invalidate_cache(['qty_available'])
            self.env.clear_cache()

            # Refresh the product to get the latest quantity
            product = self.env['product.template'].browse(product.id)

            _logger.info("Successfully set quantity for %s to %s (verified: %s)",
                        product.name, quantity, product.qty_available)

            # If there's still an issue, try a more direct approach
            if abs(product.qty_available - quantity) > 0.001:
                _logger.warning("Quantity mismatch for %s: expected %s, got %s. Trying direct method.",
                               product.name, quantity, product.qty_available)

                # Try a more direct approach using SQL (as a last resort)
                self._force_quantity_direct(variant.id, location.id, quantity)

                # Invalidate cache again
                self.env.cache.invalidate()
                product.invalidate_cache(['qty_available'])
                self.env.clear_cache()

                # Refresh the product again
                product = self.env['product.template'].browse(product.id)
                _logger.info("After direct update, quantity for %s: %s", product.name, product.qty_available)

            return True
        except Exception as e:
            _logger.error("Error setting quantity for %s: %s", product.name, str(e))
            return False

    def _force_quantity_direct(self, product_id, location_id, quantity):
        """
        Force quantity update using a more direct approach.
        This is a fallback method when the standard approach fails.

        Args:
            product_id: The product variant ID
            location_id: The stock location ID
            quantity: The quantity to set
        """
        try:
            # First, delete existing quants
            self.env.cr.execute("""
                DELETE FROM stock_quant
                WHERE product_id = %s AND location_id = %s
            """, (product_id, location_id))

            # Then create a new quant with the correct quantity
            if quantity > 0:
                self.env.cr.execute("""
                    INSERT INTO stock_quant (product_id, location_id, quantity, company_id, in_date)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (product_id, location_id, quantity, self.env.company.id))

            _logger.info("Direct quantity update completed for product_id %s", product_id)
        except Exception as e:
            _logger.error("Error in direct quantity update: %s", str(e))

    def _update_inventory_quantity(self):
        """Update inventory quantity based on apartment state"""
        for product in self:
            if product.is_apartment:
                try:
                    # Call our improved _force_inventory_quantity method
                    # It will determine the correct quantity based on apartment_state
                    result = self._force_inventory_quantity(product)
                    if not result:
                        _logger.warning("Failed to update inventory quantity for %s. Will try again later.", product.name)
                        # Log the failure but don't create a cron job during the transaction
                        # We'll try again later through the UI
                        _logger.warning("Failed to update inventory quantity for %s. Please use the 'Update Quantity' button.", product.name)
                except Exception as e:
                    _logger.error("Error updating inventory quantity for product %s: %s", product.name, str(e))



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
        """Create a new reservation (quotation) for this apartment"""
        self.ensure_one()

        if not self.is_apartment:
            raise UserError(_("This action is only available for apartments."))

        # Check if apartment is available
        if self.apartment_state != 'available':
            raise UserError(_("Only available apartments can be reserved."))

        # Check if we have an apartment_id
        if not self.apartment_id:
            raise UserError(_("This apartment is not properly linked to a real estate apartment."))

        # Create a new quotation with this apartment
        SaleOrder = self.env['sale.order']

        # Generate a detailed description for the apartment
        apartment = self.apartment_id
        project_name = apartment.project_id.name if apartment.project_id else "N/A"
        building_name = apartment.building_id.name if apartment.building_id else "N/A"
        floor = apartment.floor if apartment.floor is not None else "N/A"
        area = apartment.area if apartment.area else "N/A"
        rooms = apartment.rooms if apartment.rooms else "N/A"
        bathrooms = apartment.bathrooms if apartment.bathrooms else "N/A"

        apartment_description = f"""
Projet: {project_name}
Bâtiment: {building_name}
Appartement: {apartment.name}
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
                'product_id': self.product_variant_id.id,
                'apartment_id': self.apartment_id.id,
                'building_id': self.building_id.id if self.building_id else False,
                'product_uom_qty': 1,
                'price_unit': self.list_price,
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

    def action_open_quants(self):
        """Open the stock quants view for this apartment"""
        self.ensure_one()

        if not self.is_apartment:
            raise UserError(_("This action is only available for apartments."))

        # Get the product variant
        product_variant = self.product_variant_ids[0] if self.product_variant_ids else False
        if not product_variant:
            raise UserError(_("No product variant found for this apartment."))

        # Open the stock quants view
        return {
            'name': _('Stock On Hand'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('product_id', '=', product_variant.id), ('location_id.usage', '=', 'internal')],
            'context': {
                'search_default_internal_loc': 1,
                'search_default_productgroup': 1,
            }
        }

    def action_update_quantity(self):
        """Update the quantity based on apartment state"""
        self.ensure_one()

        if not self.is_apartment:
            raise UserError(_("This action is only available for apartments."))

        # Use our improved method to set the quantity
        # It will determine the correct quantity based on apartment_state
        result = self._force_inventory_quantity(self)

        if not result:
            raise UserError(_("Failed to update quantity. Please try again."))

        # Force a full cache invalidation to ensure UI is updated
        self.env.cache.invalidate()
        self.invalidate_cache(['qty_available'])
        self.env.clear_cache()

        # Reload the record to get fresh data
        self = self.browse(self.id)

        # Log the updated quantity
        _logger.info("After action_update_quantity, quantity for %s: %s", self.name, self.qty_available)

        # If quantity is still not correct, try the direct method
        expected_qty = 1.0 if self.apartment_state == 'available' else 0.0
        if abs(self.qty_available - expected_qty) > 0.001:
            _logger.warning("Quantity still incorrect after update. Using direct method.")

            # Get the product variant and location
            variant = self.product_variant_ids[0] if self.product_variant_ids else False
            if variant:
                warehouse = self.env['stock.warehouse'].search([], limit=1)
                if warehouse:
                    location = warehouse.lot_stock_id
                    # Use direct method
                    self._force_quantity_direct(variant.id, location.id, expected_qty)

                    # Invalidate cache again
                    self.env.cache.invalidate()
                    self.invalidate_cache(['qty_available'])
                    self.env.clear_cache()

                    # Reload the record again
                    self = self.browse(self.id)
                    _logger.info("After direct update in action_update_quantity, quantity for %s: %s",
                                self.name, self.qty_available)

        # Return a notification and reload the view to show updated quantity
        message = _('The quantity has been updated to 1 for available apartment.') if self.apartment_state == 'available' else _('The quantity has been updated to 0.')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Quantity Updated'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }

    def _post_commit_update_quantity(self, product_id):
        """Update quantity after the transaction is committed"""
        try:
            # Get the product with a new cursor to ensure we're in a new transaction
            with api.Environment.manage():
                new_cr = self.pool.cursor()
                try:
                    with api.Environment(new_cr, self.env.uid, self.env.context) as new_env:
                        product = new_env['product.template'].browse(product_id)
                        if product.exists() and product.is_apartment:
                            _logger.info("Post-commit: Updating quantity for %s", product.name)

                            # Use the standard method to update quantity
                            if product.apartment_state == 'available':
                                # Get the product variant and location
                                if product.product_variant_ids:
                                    variant = product.product_variant_ids[0]
                                    warehouse = new_env['stock.warehouse'].search([], limit=1)
                                    if warehouse:
                                        location = warehouse.lot_stock_id

                                        # Use the standard method to update quantity
                                        StockQuant = new_env['stock.quant']

                                        # First, remove existing quants
                                        quants = StockQuant.search([
                                            ('product_id', '=', variant.id),
                                            ('location_id', '=', location.id)
                                        ])

                                        if quants:
                                            quants.sudo().unlink()

                                        # Create a new quant with quantity 1
                                        StockQuant.sudo().create({
                                            'product_id': variant.id,
                                            'location_id': location.id,
                                            'quantity': 1.0,
                                            'company_id': new_env.company.id,
                                            'in_date': fields.Datetime.now(),
                                        })

                                        new_cr.commit()
                                        _logger.info("Post-commit: Successfully updated quantity for %s", product.name)
                except Exception as e:
                    _logger.error("Error in post-commit quantity update: %s", str(e))
                    new_cr.rollback()
                finally:
                    new_cr.close()
        except Exception as e:
            _logger.error("Failed to create new cursor for post-commit update: %s", str(e))

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
