# Real Estate Module for Odoo 14

This module provides a complete solution for managing real estate projects, buildings, and apartments in Odoo 14, fully integrated with the standard sales module.

## Requirements

- Odoo 14.0
- PostgreSQL 13
- Python 3.8

## Features

- **Hierarchical Structure**: Projects (Categories) → Buildings (Sub-categories) → Apartments (Products)
- **Project Management**: Create and manage real estate projects with details like name, city, and logo
- **Building Management**: Manage buildings within projects, including number of floors
- **Apartment Management**: Track apartments with details like floor, area, price, and status
- **Sales Integration**: Fully integrated with Odoo's native sales module
- **Dashboard**: View key metrics and statistics

## Installation

### Method 1: Using the Module Installer

1. Download the module as a ZIP file
2. Go to Odoo Apps menu
3. Click on "Upload a Module" button
4. Select the downloaded ZIP file
5. Click "Install" button

### Method 2: Manual Installation

1. Extract the downloaded module to your Odoo addons directory
   ```
   /path/to/odoo/addons/
   ```

2. Restart Odoo server
   ```
   service odoo restart
   ```
   or
   ```
   systemctl restart odoo
   ```

3. Update the module list in Odoo
   - Go to Apps menu
   - Click on "Update Apps List" button
   - Search for "Real Estate Reservation"
   - Click "Install" button

## Configuration

After installation:

1. Go to Real Estate → Properties → Projects
   - Create your real estate projects

2. For each project, create buildings and apartments

3. Use the standard Odoo Sales module to sell apartments

## Dependencies

This module depends on the following Odoo modules:
- base
- mail
- sale_management
- product
- stock
- sale_stock

## Support

For any questions or support, please contact the module author.

## License

This module is licensed under LGPL-3.
