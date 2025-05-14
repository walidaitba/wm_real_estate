odoo.define('wm_real_estate.apartment_buttons', function (require) {
    "use strict";

    // Debug flag - set to true to enable detailed logging
    var DEBUG = true;

    // Helper function for logging
    function debug(message) {
        if (DEBUG) {
            console.log("[APARTMENT_BUTTONS] " + message);
        }
    }

    // Log module initialization with timestamp
    debug("Module initializing at " + new Date().toISOString());

    // We're no longer adding buttons to the list view since we're using the modal approach
    // The modal is implemented in apartment_action.js

    // Log that the module has been loaded
    debug("Module loaded successfully");
});
