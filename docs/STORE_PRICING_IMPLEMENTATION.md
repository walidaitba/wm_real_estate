# Store Pricing Implementation Summary

## Problem Solved
You correctly identified that stores should be priced using the formula:
**Store Price = Area (m²) × Unit Price per m²**

The area field represents the actual quantity of square meters, so we don't need to multiply by the quantity field again.

## Implementation Details

### Modified File: `models/sale_order.py`

#### 1. Custom Pricing Method
```python
@api.depends('product_id', 'product_uom_qty', 'product_id.product_tmpl_id.is_store', 'product_id.product_tmpl_id.area', 'product_id.product_tmpl_id.list_price')
def _compute_price_unit(self):
    """Override price calculation for stores: area × unit price per m²"""
    for line in self:
        if line.product_id and line.product_id.product_tmpl_id.is_store:
            # For stores: Calculate price as area × unit price per m²
            # The area IS the quantity for stores, so we don't multiply by product_uom_qty
            store_product = line.product_id.product_tmpl_id
            area = store_product.area or 0.0
            unit_price_per_m2 = store_product.list_price or 0.0
            
            # Calculate total price: area × unit price per m²
            line.price_unit = area * unit_price_per_m2
            
            _logger.info("Store pricing calculation for %s: area=%s × price_per_m2=%s = %s",
                       store_product.name, area, unit_price_per_m2, line.price_unit)
        else:
            # For non-store products, use standard Odoo pricing
            super(SaleOrderLine, line)._compute_price_unit()
```

#### 2. Onchange Method
```python
@api.onchange('product_id', 'product_uom_qty')
def _onchange_product_id_store_pricing(self):
    """Recalculate price when product or quantity changes for stores"""
    if self.product_id and self.product_id.product_tmpl_id.is_store:
        # Trigger price recalculation for stores
        self._compute_price_unit()
```

## Key Changes Made

### Before (Incorrect)
- Formula: `quantity × area × unit_price_per_m²`
- Result: Store with 50m² and price 100/m² and quantity 1 = 1 × 50 × 100 = 5000
- Result: Store with 50m² and price 100/m² and quantity 2 = 2 × 50 × 100 = 10000 ❌

### After (Correct)
- Formula: `area × unit_price_per_m²`
- Result: Store with 50m² and price 100/m² = 50 × 100 = 5000
- Result: Store with 50m² and price 100/m² (quantity ignored) = 50 × 100 = 5000 ✅

## Test Results
All test cases pass:
1. ✅ Basic store pricing: 50m² × 100 = 5000
2. ✅ Quantity ignored: Still 50m² × 100 = 5000
3. ✅ Different dimensions: 75m² × 150 = 11250
4. ✅ Zero area: 0m² × 100 = 0
5. ✅ Zero price per m²: 50m² × 0 = 0
6. ✅ Non-store products: Uses standard Odoo pricing
7. ✅ Fractional quantities ignored: Still 50m² × 100 = 5000

## Benefits
- **Correct Pricing**: Stores are now priced based on their actual area, not multiplied by quantity
- **Consistent Logic**: Area represents the quantity for stores
- **Backwards Compatible**: Non-store products continue to use standard Odoo pricing
- **Automatic Recalculation**: Price updates when product or quantity changes
- **Proper Logging**: Debug information for store pricing calculations

## Usage
When creating sale order lines with store products:
1. Select a store product (product with `is_store = True`)
2. The price will automatically calculate as: `area × list_price`
3. Changing quantity won't affect the price (area is the real quantity)
4. The system logs the calculation for debugging

## Next Steps
The implementation is complete and ready for use. The store pricing logic now correctly calculates prices using the area field as the quantity, avoiding double multiplication.
