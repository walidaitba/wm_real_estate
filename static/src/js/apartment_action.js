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
            debug(propertyType + " state: " + propertyData.apartment_state + ", qty_available: " + propertyData.qty_available);

            // Add buttons based on property state
            if (propertyData.apartment_state === 'disponible') {
                // For disponible properties: only Reserve and View Details buttons (no Cancel)
                buttons.push({
                    text: _t('Réserver'),
                    classes: 'btn-primary',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'action_create_reservation',
                            args: [[propertyData.id]],
                        }).then(function (action) {
                            dialog.close();
                            if (action && action.type) {
                                debug("Executing action: " + JSON.stringify(action));
                                self.do_action(action);
                            } else {
                                debug("Invalid action received: " + JSON.stringify(action));
                                self.displayNotification({
                                    title: _t('Erreur'),
                                    message: _t('Impossible de créer la réservation. Veuillez réessayer.'),
                                    type: 'danger'
                                });
                            }
                        }).guardedCatch(function (error) {
                            dialog.close();
                            debug("Error creating reservation: " + JSON.stringify(error));
                            self.displayNotification({
                                title: _t('Erreur'),
                                message: _t('Impossible de créer la réservation. Veuillez réessayer.'),
                                type: 'danger'
                            });
                        });
                    }
                });
            } else if (propertyData.apartment_state === 'prereserved') {
                // For prereserved properties: Cancel Reservation and Confirm Reservation buttons
                buttons.push({
                    text: _t('Annuler la réservation'),
                    classes: 'btn-warning',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'action_cancel_reservation',
                            args: [[propertyData.id]],
                        }).then(function (result) {
                            dialog.close();
                            if (result) {
                                debug("Reservation cancelled successfully");
                                // Reload the view to reflect the changes
                                self.reload();
                            } else {
                                debug("Error cancelling reservation");
                                self.displayNotification({
                                    title: _t('Erreur'),
                                    message: _t('Impossible d\'annuler la réservation. Veuillez réessayer.'),
                                    type: 'danger'
                                });
                            }
                        }).guardedCatch(function (error) {
                            dialog.close();
                            debug("Error cancelling reservation: " + JSON.stringify(error));
                            self.displayNotification({
                                title: _t('Erreur'),
                                message: _t('Impossible d\'annuler la réservation. Veuillez réessayer.'),
                                type: 'danger'
                            });
                        });
                    }
                });

                buttons.push({
                    text: _t('Confirmer la réservation'),
                    classes: 'btn-success',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'action_confirm_reservation',
                            args: [[propertyData.id]],
                        }).then(function (action) {
                            dialog.close();
                            if (action && action.type) {
                                debug("Executing confirm reservation action: " + JSON.stringify(action));
                                self.do_action(action);
                            } else {
                                debug("Invalid action received from confirm reservation: " + JSON.stringify(action));
                                self.displayNotification({
                                    title: _t('Erreur'),
                                    message: _t('Impossible d\'ouvrir le devis. Veuillez réessayer.'),
                                    type: 'danger'
                                });
                            }
                        }).guardedCatch(function (error) {
                            dialog.close();
                            debug("Error confirming reservation: " + JSON.stringify(error));
                            self.displayNotification({
                                title: _t('Erreur'),
                                message: _t('Impossible d\'ouvrir le devis. Veuillez réessayer.'),
                                type: 'danger'
                            });
                        });
                    }
                });
            } else if (propertyData.apartment_state === 'sold') {
                // For sold properties: only Fiche Reservation button
                buttons.push({
                    text: _t('Fiche de Réservation'),
                    classes: 'btn-info',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'action_view_reservation_document',
                            args: [[propertyData.id]],
                        }).then(function (action) {
                            dialog.close();
                            if (action && action.type) {
                                debug("Executing view reservation document action: " + JSON.stringify(action));
                                self.do_action(action);
                            } else {
                                debug("Invalid action received from view reservation document: " + JSON.stringify(action));
                                self.displayNotification({
                                    title: _t('Erreur'),
                                    message: _t('Impossible d\'ouvrir le document de réservation. Veuillez réessayer.'),
                                    type: 'danger'
                                });
                            }
                        }).guardedCatch(function (error) {
                            dialog.close();
                            debug("Error viewing reservation document: " + JSON.stringify(error));
                            self.displayNotification({
                                title: _t('Erreur'),
                                message: _t('Impossible d\'ouvrir le document de réservation. Veuillez réessayer.'),
                                type: 'danger'
                            });
                        });
                    }
                });
            }

            // Add view details button only for disponible properties
            if (propertyData.apartment_state === 'disponible') {
                buttons.push({
                    text: isApartment ? _t('Voir l\'appartement') : _t('Voir le magasin'),
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
                                title: _t('Erreur'),
                                message: _t('Impossible d\'ouvrir les détails de la propriété. Veuillez réessayer.'),
                                type: 'danger'
                            });
                        }
                    }
                });
            }

            // Create and display the dialog
            var dialog = new Dialog(this, {
                title: isApartment ? _t('Options Appartement : ') + propertyData.name : _t('Options Magasin : ') + propertyData.name,
                size: 'medium',
                buttons: buttons,
                $content: this._preparePropertyModalContent(propertyData),
                technical: false,
                dialogClass: 'o_property_dialog'
            });

            dialog.open();
        },

        /**
         * Prepare the content for the property modal
         */
        _preparePropertyModalContent: function (property) {
            var $content = $('<div>').addClass('p-3 property-modal-content');
            var isApartment = property.is_apartment === true;

            // Status with updated colors
            var statusClass = 
                property.apartment_state === 'disponible' ? 'info' :
                property.apartment_state === 'prereserved' ? 'danger' : 
                property.apartment_state === 'sold' ? 'success' : 'secondary';

            var statusText = 
                property.apartment_state === 'disponible' ? _t('Disponible') :
                property.apartment_state === 'prereserved' ? _t('Préréservé') : 
                property.apartment_state === 'sold' ? _t('Vendu') : '';

            $content.append($('<div>').addClass('mb-3').append(
                $('<strong>').text(_t('Statut : ')),
                $('<span>').addClass('badge badge-' + statusClass).text(statusText)
            ));

            // Property type indicator
            $content.append($('<div>').addClass('mb-3').append(
                $('<strong>').text(_t('Type : ')),
                $('<span>').addClass('badge badge-info').text(isApartment ? _t('Appartement') : _t('Magasin'))
            ));

            // Create two columns
            var $row = $('<div>').addClass('row');
            var $col1 = $('<div>').addClass('col-12 col-sm-6');
            var $col2 = $('<div>').addClass('col-12 col-sm-6');

            // We're not showing project and building fields as requested

            if (property.floor !== undefined) {
                $col2.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Étage : ')),
                    document.createTextNode(property.floor)
                ));
            }

            if (property.area !== undefined) {
                $col2.append($('<div>').addClass('mb-2').append(
                    $('<strong>').text(_t('Surface : ')),
                    document.createTextNode(property.area + ' m²')
                ));
            }

            // Add rooms and bathrooms only for apartments
            if (isApartment) {
                if (property.rooms !== undefined) {
                    $col1.append($('<div>').addClass('mb-2').append(
                        $('<strong>').text(_t('chambres : ')),
                        document.createTextNode(property.rooms)
                    ));
                }

                if (property.bathrooms !== undefined) {
                    $col2.append($('<div>').addClass('mb-2').append(
                        $('<strong>').text(_t('Salles de bain : ')),
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
