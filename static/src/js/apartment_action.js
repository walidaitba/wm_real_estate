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
                record && record.data && (record.data.is_apartment === true || record.data.is_store === true || record.data.is_equipement === true)) {

                // Prevent default action
                event.stopPropagation();

                // Log the record data for debugging
                if (record.data.is_apartment) {
                    debug("Apartment data: " + JSON.stringify(record.data));
                } else if (record.data.is_store) {
                    debug("Store data: " + JSON.stringify(record.data));
                } else {
                    debug("Équipement data: " + JSON.stringify(record.data));
                }

                // Show property options dialog
                this._showPropertyOptions(record.data);

                return;
            }

            // Call the original method for non-apartment records
            this._super.apply(this, arguments);
        },

        /**
         * Show property options in a dialog (for apartments, stores, and équipements)
         */
        _showPropertyOptions: function (propertyData) {
            var self = this;
            var buttons = [];
            var isApartment = propertyData.is_apartment === true;
            var isStore = propertyData.is_store === true;
            var isEquipement = propertyData.is_equipement === true;
            var propertyType = isApartment ? 'apartment' : (isStore ? 'store' : 'équipement');

            debug("Showing " + propertyType + " options dialog for: " + propertyData.name);
            debug(propertyType + " state: " + propertyData.apartment_state + ", qty_available: " + propertyData.qty_available);

            // Add buttons based on property state
            if (propertyData.apartment_state === 'disponible') {
                // For disponible properties: Reserve, Bloquer and View Details buttons
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

                // Add Bloquer button for disponible properties
                buttons.push({
                    text: 'Bloquer',
                    classes: 'btn-warning',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'write',
                            args: [[propertyData.id], {'sale_ok': false}],
                        }).then(function (result) {
                            dialog.close();
                            if (result) {
                                debug(propertyType + " blocked successfully");
                                // Reload the view to reflect the changes
                                self.reload();
                                self.displayNotification({
                                    title: 'Succès',
                                    message: 'La propriété a été bloquée avec succès.',
                                    type: 'success'
                                });
                            } else {
                                debug("Error blocking " + propertyType);
                                self.displayNotification({
                                    title: _t('Erreur'),
                                    message: 'Impossible de bloquer la propriété. Veuillez réessayer.',
                                    type: 'danger'
                                });
                            }
                        }).guardedCatch(function (error) {
                            dialog.close();
                            debug("Error blocking " + propertyType + ": " + JSON.stringify(error));
                            self.displayNotification({
                                title: _t('Erreur'),
                                message: 'Impossible de bloquer la propriété. Veuillez réessayer.',
                                type: 'danger'
                            });
                        });
                    }
                });
            } else if (propertyData.apartment_state === 'blocker') {
                // For blocker properties: Add Débloquer button
                buttons.push({
                    text: 'Débloquer',
                    classes: 'btn-success',
                    click: function () {
                        self._rpc({
                            model: 'product.template',
                            method: 'write',
                            args: [[propertyData.id], {'sale_ok': true}],
                        }).then(function (result) {
                            dialog.close();
                            if (result) {
                                debug(propertyType + " unblocked successfully");
                                // Reload the view to reflect the changes
                                self.reload();
                                self.displayNotification({
                                    title: 'Succès',
                                    message: 'La propriété a été débloquée avec succès.',
                                    type: 'success'
                                });
                            } else {
                                debug("Error unblocking " + propertyType);
                                self.displayNotification({
                                    title: _t('Erreur'),
                                    message: 'Impossible de débloquer la propriété. Veuillez réessayer.',
                                    type: 'danger'
                                });
                            }
                        }).guardedCatch(function (error) {
                            dialog.close();
                            debug("Error unblocking " + propertyType + ": " + JSON.stringify(error));
                            self.displayNotification({
                                title: _t('Erreur'),
                                message: 'Impossible de débloquer la propriété. Veuillez réessayer.',
                                type: 'danger'
                            });
                        });
                    }
                });
                debug(propertyType + " is blocked - Débloquer button added");
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
                    text: _t('Voire la réservation'),
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
                // For sold properties: Fiche Reservation button and Cancel Sale button
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

                // Add Cancel Sale button for sold properties
                buttons.push({
                    text: _t('Annuler la vente'),
                    classes: 'btn-danger',
                    click: function () {
                        // Show confirmation dialog first
                        var confirmDialog = new Dialog(self, {
                            title: _t('Confirmer l\'annulation'),
                            size: 'medium',
                            $content: $('<div>').html(
                                '<p>' + _t('Êtes-vous sûr de vouloir annuler la vente de cette propriété ?') + '</p>' +
                                '<p><strong>' + _t('Attention: Cette action:') + '</strong></p>' +
                                '<ul>' +
                                '<li>' + _t('Annulera les commandes de vente confirmées') + '</li>' +
                                '<li>' + _t('Remettra la propriété en état "Disponible"') + '</li>' +
                                '<li>' + _t('Conservera les factures existantes (créez des avoirs si nécessaire)') + '</li>' +
                                '</ul>'
                            ),
                            buttons: [
                                {
                                    text: _t('Annuler'),
                                    classes: 'btn-secondary',
                                    close: true
                                },
                                {
                                    text: _t('Confirmer l\'annulation'),
                                    classes: 'btn-danger',
                                    click: function () {
                                        confirmDialog.close();
                                        dialog.close();
                                        
                                        // Perform the cancellation
                                        self._rpc({
                                            model: 'product.template',
                                            method: 'action_cancel_sold_property',
                                            args: [[propertyData.id]],
                                        }).then(function (result) {
                                            if (result) {
                                                debug("Sold property cancelled successfully");
                                                // Reload the view to reflect the changes
                                                self.reload();
                                                // The success notification is handled by the backend method
                                            } else {
                                                debug("Error cancelling sold property");
                                                self.displayNotification({
                                                    title: _t('Erreur'),
                                                    message: _t('Impossible d\'annuler la vente. Veuillez réessayer.'),
                                                    type: 'danger'
                                                });
                                            }
                                        }).guardedCatch(function (error) {
                                            debug("Error cancelling sold property: " + JSON.stringify(error));
                                            self.displayNotification({
                                                title: _t('Erreur'),
                                                message: _t('Impossible d\'annuler la vente. Veuillez réessayer.'),
                                                type: 'danger'
                                            });
                                        });
                                    }
                                }
                            ]
                        });
                        confirmDialog.open();
                    }
                });
            }

            // Add view details button for disponible and blocker properties
            if (propertyData.apartment_state === 'disponible' || propertyData.apartment_state === 'blocker') {
                buttons.push({
                    text: isApartment ? _t('Voir l\'appartement') : (isStore ? _t('Voir le magasin') : _t('Voir l\'équipement')),
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
                title: isApartment ? _t('Options Appartement : ') + propertyData.name : 
                       (isStore ? _t('Options Magasin : ') + propertyData.name : _t('Options Équipement : ') + propertyData.name),
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
            var isStore = property.is_store === true;
            var isEquipement = property.is_equipement === true;

            // Status with updated colors
            var statusClass = 
                property.apartment_state === 'disponible' ? 'info' :
                property.apartment_state === 'prereserved' ? 'danger' : 
                property.apartment_state === 'sold' ? 'success' : 
                property.apartment_state === 'blocker' ? 'warning' : 'secondary';

            var statusText = 
                property.apartment_state === 'disponible' ? _t('Disponible') :
                property.apartment_state === 'prereserved' ? _t('Préréservé') : 
                property.apartment_state === 'sold' ? _t('Vendu') : 
                property.apartment_state === 'blocker' ? _t('Bloqué') : '';

            $content.append($('<div>').addClass('mb-3').append(
                $('<strong>').text(_t('Statut : ')),
                $('<span>').addClass('badge badge-' + statusClass).text(statusText)
            ));

            // Add info message for blocked properties
            if (property.apartment_state === 'blocker') {
                $content.append($('<div>').addClass('alert alert-warning mb-3').append(
                    $('<i>').addClass('fa fa-exclamation-triangle mr-2'),
                    $('<span>').text(_t('Cette propriété est actuellement bloquée et ne peut pas être vendue.'))
                ));
            }

            // Property type indicator
            $content.append($('<div>').addClass('mb-3').append(
                $('<strong>').text(_t('Type : ')),
                $('<span>').addClass('badge badge-info').text(isApartment ? _t('Appartement') : (isStore ? _t('Magasin') : _t('Équipement')))
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
