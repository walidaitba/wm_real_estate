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

            // Check if it's an apartment product
            if (this.modelName === 'product.template' &&
                record && record.data && record.data.is_apartment === true) {

                // Prevent default action
                event.stopPropagation();

                // Log the record data for debugging
                debug("Apartment data: " + JSON.stringify(record.data));

                // Show apartment options dialog
                this._showApartmentOptions(record.data);

                return;
            }

            // Call the original method for non-apartment records
            this._super.apply(this, arguments);
        },

        /**
         * Show apartment options in a dialog
         */
        _showApartmentOptions: function (apartmentData) {
            var self = this;
            var buttons = [];

            debug("Showing apartment options dialog for: " + apartmentData.name);

            // Add buttons based on apartment state
            debug("Apartment state: " + apartmentData.apartment_state + ", qty_available: " + apartmentData.qty_available);

            if (apartmentData.apartment_state === 'available') {
                // Always show the Reserve button for available apartments
                buttons.push({
                    text: _t('Reserve'),
                    classes: 'btn-primary',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'action_create_reservation',
                            args: [[apartmentData.id]],
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
                        debug("Opening view details for apartment: " + apartmentData.id);
                        self.do_action({
                            type: 'ir.actions.act_window',
                            res_model: 'product.template',
                            res_id: apartmentData.id,
                            views: [[false, 'form']],
                            view_mode: 'form',  // Added view_mode for compatibility
                            target: 'current',
                            context: {'form_view_ref': 'wm_real_estate.product_template_form_view_real_estate'}
                        });
                    } catch (error) {
                        debug("Error opening view details: " + error);
                        self.displayNotification({
                            title: _t('Error'),
                            message: _t('Could not open apartment details. Please try again.'),
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
                title: _t('Apartment Options: ') + apartmentData.name,
                size: 'medium',
                buttons: buttons,
                $content: this._prepareApartmentModalContent(apartmentData),
                technical: false,
                dialogClass: 'o_apartment_dialog'
            });

            dialog.open();
        },

        /**
         * Prepare the content for the apartment modal
         */
        _prepareApartmentModalContent: function (apartment) {
            var $content = $('<div>').addClass('p-3 apartment-modal-content');

            // Status
            var statusClass = apartment.apartment_state === 'available' ? 'success' :
                             apartment.apartment_state === 'reserved' ? 'warning' : 'danger';

            var statusText = apartment.apartment_state === 'available' ? _t('Available') :
                            apartment.apartment_state === 'reserved' ? _t('Reserved') : _t('Sold');

            $content.append($('<div>').addClass('mb-3').append(
                $('<strong>').text(_t('Status: ')),
                $('<span>').addClass('badge badge-' + statusClass).text(statusText)
            ));

            // Create two columns
            var $row = $('<div>').addClass('row');
            var $col1 = $('<div>').addClass('col-12 col-sm-6');
            var $col2 = $('<div>').addClass('col-12 col-sm-6');

            // We're not showing project and building fields as requested

            if (apartment.floor !== undefined) {
                $col2.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Floor: ')),
                    document.createTextNode(apartment.floor)
                ));
            }

            if (apartment.area !== undefined) {
                $col2.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Area: ')),
                    document.createTextNode(apartment.area + ' m²')
                ));
            }

            // Add rooms and bathrooms
            if (apartment.rooms !== undefined) {
                $col1.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Rooms: ')),
                    document.createTextNode(apartment.rooms)
                ));
            }

            if (apartment.bathrooms !== undefined) {
                $col2.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Bathrooms: ')),
                    document.createTextNode(apartment.bathrooms)
                ));
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
