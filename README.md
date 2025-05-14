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

### Method 3: clone repository inside addons folder

   -git clone https://walidaitba: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@github.com/walidaitba/wm_real_estate.git


## Dependencies

This module depends on the following Odoo modules:
- base
- mail
- sale_management
- product
- stock
- sale_stock
- account

# Apartment Sales Workflow Documentation

This section provides comprehensive documentation for the apartment sales workflow in the Real Estate module, from apartment creation to sale completion.

## Apartment Status Flow

Apartments in the system follow a specific status flow:

1. **Available** - The apartment is available for sale
2. **Réservation en cours** - A quotation has been created but not yet confirmed
3. **Reserved** - A quotation has been confirmed, creating a reservation
4. **Sold** - The apartment has been sold and is no longer available

The status changes automatically based on actions in the sales process:

```
Available → Réservation en cours → Reserved → Sold
```

## Step-by-Step Workflow

### Creating an Apartment

1. Navigate to **Real Estate > Properties > Apartments**
2. Click **Create**
3. Fill in the required information:
   - Apartment Number
   - Code
   - Building (must select an existing building)
   - Floor
   - Price
   - Area (m²)
   - Number of Rooms
   - Number of Bathrooms
   - Description (optional)
4. Click **Save**

The apartment will be automatically created with the status **Available**.

### Creating a Quotation/Reservation

1. Navigate to **Real Estate > Quotations > Quotations**
2. Click **Create**
3. Fill in the required information:
   - Customer
   - Project (select from dropdown)
4. In the Order Lines section, click **Add an apartment**
5. Select an apartment from the list (only available apartments will be shown)
6. Adjust the price if needed
7. Click **Save**

When an apartment is added to a quotation, its status automatically changes to **Réservation en cours**.

### Confirming a Quotation

1. Open the quotation you want to confirm
2. Click the **Confirm** button in the top-right corner
3. The system will display a success message

When a quotation is confirmed:
- The quotation becomes a sales order
- The apartment status changes to **Reserved**
- A delivery order is created for the apartment handover

### Converting a Reservation to a Sale

1. Navigate to **Real Estate > Quotations > Quotations**
2. Open the confirmed sales order (reservation)
3. Click on the apartment line to view details
4. Click the **Mark as Sold** button
5. Confirm the action

Alternatively, you can:
1. Navigate to **Real Estate > Properties > Apartments**
2. Open the reserved apartment
3. Click the **Mark as Sold** button
4. Confirm the action

When an apartment is marked as sold:
- The apartment status changes to **Sold**
- The apartment is removed from available inventory

## Configuration Settings

### Required Configuration

1. **Projects and Buildings**:
   - At least one project and building must be created before apartments can be added
   - Navigate to **Real Estate > Properties > Projects** to create projects
   - Navigate to **Real Estate > Properties > Buildings** to create buildings

2. **Product Categories**:
   - Apartments are managed as products in the inventory
   - A product category for apartments is automatically created during installation

### Optional Configuration

1. **Sales Teams**:
   - You can assign specific sales teams to handle real estate sales
   - Navigate to **Sales > Configuration > Sales Teams**

2. **Accounting Integration**:
   - Configure income accounts for apartment sales
   - Navigate to **Accounting > Configuration > Chart of Accounts**





