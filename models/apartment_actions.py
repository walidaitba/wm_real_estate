from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)

class ApartmentActions(models.Model):
    _name = 'apartment.actions'
    _description = 'Apartment Actions'
    _auto = False

    @api.model
    def init(self):
        """Initialize the model"""
        # This is a transient model, so no need to create a table
        pass

    @api.model
    def get_apartment_action(self, action_ref, domain=None, context=None):
        """Get the apartment action with custom views"""
        # Get the action
        action = self.env.ref(action_ref).read()[0]

        # Update domain if provided
        if domain:
            action['domain'] = domain

        # Update context if provided
        if context:
            action['context'] = context

        # Get the custom views
        try:
            # Try to get the apartment list view
            apartment_list_view = self.env.ref('wm_real_estate.product_template_apartment_list_view')
            apartment_form_view = self.env.ref('wm_real_estate.product_template_form_view_real_estate')

            # Set the views
            action['views'] = [
                (apartment_list_view.id, 'tree'),
                (apartment_form_view.id, 'form')
            ]

            # Make sure the js_class is used
            action['view_type'] = 'list'
            action['flags'] = {
                'action_buttons': True,
                'hasSearchView': True,
            }
        except Exception as e:
            _logger.error("Error getting apartment views: %s", str(e))

        return action
