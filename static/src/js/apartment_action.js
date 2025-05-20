odoo.define('wm_real_estate.apartment_action', function (require) {
    "use strict";

    var core = require('web.core');
    var ListController = require('web.ListController');
    var Dialog = require('web.Dialog');
    var _t = core._t;

    // Debug flag - set to true to enable detailed logging
    var DEBUG = true;

    // Helper function for logging
    function debug(message) {
        if (DEBUG) {
            console.log("[APARTMENT_ACTION] " + message);
        }
    }

    // Log module initialization with timestamp
    debug("Module initializing at " + new Date().toISOString());

    ListController.include({
        /**
         * Override to add custom action for apartments
         */
        _onOpenRecord: function (event) {
            var record = this.model.get(event.data.id);

            // Only handle product.template records, not real.estate.apartment records
            // This ensures we don't interfere with the apartment kanban view
            if (this.modelName === 'product.template' &&
                record && record.data && (record.data.is_apartment === true || record.data.is_store === true)) {

                // Prevent default action
                event.stopPropagation();

                // Log the record data for debugging
                if (record.data.is_apartment) {
                    debug("Apartment data: " + JSON.stringify(record.data));
                } else {
                    debug("Store data: " + JSON.stringify(record.data));
                }

                // Show property options dialog
                this._showPropertyOptions(record.data);

                return;
            }

            // Call the original method for non-apartment records
            this._super.apply(this, arguments);
        },

        /**
         * Show property options in a dialog (for both apartments and stores)
         */
        _showPropertyOptions: function (propertyData) {
            var self = this;
            var buttons = [];
            var isApartment = propertyData.is_apartment === true;
            var propertyType = isApartment ? 'apartment' : 'store';

            debug("Showing " + propertyType + " options dialog for: " + propertyData.name);

            // Add buttons based on property state
            debug(propertyType + " state: " + propertyData.apartment_state + ", qty_available: " + propertyData.qty_available);

            if (propertyData.apartment_state === 'available') {
                // Always show the Reserve button for available properties
                buttons.push({
                    text: _t('Reserve'),
                    classes: 'btn-primary',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'action_create_reservation',
                            args: [[propertyData.id]],
                        }).then(function (action) {
                            dialog.close();
                            // Make sure action is valid before doing it
                            if (action && action.type) {
                                debug("Executing action: " + JSON.stringify(action));
                                self.do_action(action);
                            } else {
                                debug("Invalid action received: " + JSON.stringify(action));
                                self.displayNotification({
                                    title: _t('Error'),
                                    message: _t('Could not create reservation. Please try again or contact your administrator.'),
                                    type: 'danger'
                                });
                            }
                        }).guardedCatch(function (error) {
                            dialog.close();
                            debug("Error creating reservation: " + JSON.stringify(error));
                            self.displayNotification({
                                title: _t('Error'),
                                message: _t('Could not create reservation. Please try again or contact your administrator.'),
                                type: 'danger'
                            });
                        });
                    }
                });
            }

            // Add view details button
            buttons.push({
                text: _t('View Details'),
                classes: 'btn-secondary',
                click: function () {
                    dialog.close();
                    try {
                        debug("Opening view details for " + propertyType + ": " + propertyData.id);
                        self.do_action({
                            type: 'ir.actions.act_window',
                            res_model: 'product.template',
                            res_id: propertyData.id,
                            views: [[false, 'form']],
                            view_mode: 'form',  // Added view_mode for compatibility
                            target: 'current',
                            context: {'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate'}
                        });
                    } catch (error) {
                        debug("Error opening view details: " + error);
                        self.displayNotification({
                            title: _t('Error'),
                            message: _t('Could not open property details. Please try again.'),
                            type: 'danger'
                        });
                    }
                }
            });

            // Add cancel button
            buttons.push({
                text: _t('Cancel'),
                close: true
            });

            // Create and display the dialog
            var dialog = new Dialog(this, {
                title: isApartment ? _t('Apartment Options: ') + propertyData.name : _t('Store Options: ') + propertyData.name,
                size: 'medium',
                buttons: buttons,
                $content: this._preparePropertyModalContent(propertyData),
                technical: false,
                dialogClass: 'o_property_dialog',
                // Add a custom destroy method to handle the canBeRemoved error
                destroy: function() {
                    try {
                        // Call the original destroy method
                        Dialog.prototype.destroy.call(this);
                    } catch (error) {
                        debug("Error during dialog destroy: " + error);
                        // Force remove the dialog from the DOM if there's an error
                        if (this.$el) {
                            this.$el.remove();
                        }
                    }
                }
            });

            // Add a custom close method to handle the canBeRemoved error
            var originalClose = dialog.close;
            dialog.close = function() {
                try {
                    // Call the original close method
                    originalClose.call(this);
                } catch (error) {
                    debug("Error during dialog close: " + error);
                    // Force remove the dialog from the DOM if there's an error
                    if (this.$el) {
                        this.$el.remove();
                    }
                    // Force destroy the dialog
                    this.destroy();
                }
            };

            dialog.open();
        },

        /**
         * Prepare the content for the property modal (apartment or store)
         */
        _preparePropertyModalContent: function (property) {
            var $content = $('<div>').addClass('p-3 property-modal-content');
            var isApartment = property.is_apartment === true;

            // Status
            var statusClass = property.apartment_state === 'available' ? 'success' :
                             property.apartment_state === 'reserved' ? 'warning' : 'danger';

            var statusText = property.apartment_state === 'available' ? _t('Available') :
                            property.apartment_state === 'reserved' ? _t('Reserved') : _t('Sold');

            $content.append($('<div>').addClass('mb-3').append(
                $('<strong>').text(_t('Status: ')),
                $('<span>').addClass('badge badge-' + statusClass).text(statusText)
            ));

            // Property type indicator
            $content.append($('<div>').addClass('mb-3').append(
                $('<strong>').text(_t('Type: ')),
                $('<span>').addClass('badge badge-info').text(isApartment ? _t('Apartment') : _t('Store'))
            ));

            // Create two columns
            var $row = $('<div>').addClass('row');
            var $col1 = $('<div>').addClass('col-12 col-sm-6');
            var $col2 = $('<div>').addClass('col-12 col-sm-6');

            // We're not showing project and building fields as requested

            if (property.floor !== undefined) {
                $col2.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Floor: ')),
                    document.createTextNode(property.floor)
                ));
            }

            if (property.area !== undefined) {
                $col2.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Area: ')),
                    document.createTextNode(property.area + ' m²')
                ));
            }

            // Add rooms and bathrooms only for apartments
            if (isApartment) {
                if (property.rooms !== undefined) {
                    $col1.append($('<div>').addClass('mb-2').append(
                        $('<strong>').text(_t('Rooms: ')),
                        document.createTextNode(property.rooms)
                    ));
                }

                if (property.bathrooms !== undefined) {
                    $col2.append($('<div>').addClass('mb-2').append(
                        $('<strong>').text(_t('Bathrooms: ')),
                        document.createTextNode(property.bathrooms)
                    ));
                }
            }

            // Add columns to row
            $row.append($col1).append($col2);
            $content.append($row);

            return $content;
        }
    });

    // Log that the module has been loaded
    debug("Module loaded successfully");
});
