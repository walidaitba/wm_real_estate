# Real Estate Apartment/Store Status Logic

## Status Types

### New Status Flow
1. **Disponible (Available)** - Light Blue
   - Initial state
   - Can create new quotation
   - Visible in available count

2. **Préréservé (Pre-reserved)** - Red
   - Automatically set when quotation is created
   - Still counts in "available" total (available = disponible + préréservé)
   - Can be cancelled back to "disponible"
   - Shows in pre-reserved filter/count

3. **Vendu (Sold)** - Green
   - Set automatically when quotation is confirmed to sales order
   - Final state
   - Cannot be reversed without special access

### Removed States
- "Réservation en cours" state removed
- "Reserved" state renamed to "Préréservé"

## Status Transitions

### From Disponible:
- Can create quotation → moves to Préréservé
- Shows in available totals

### From Préréservé:
- Cancel reservation → returns to Disponible
- Confirm quotation → moves to Vendu
- Still counts in available totals
- Shows "Cancel Reservation" button in modal
- Locked for other quotations

### From Vendu:
- Final state
- Cannot be modified without special access
- No transition buttons shown

## Automatic Transitions

1. **Create Quotation**
   - Initial State: Disponible
   - Action: Create quotation
   - Result: Status changes to Préréservé
   - System: Automatic on quotation creation

2. **Confirm Sale**
   - Initial State: Préréservé
   - Action: Confirm quotation (to sales order)
   - Result: Status changes to Vendu
   - System: Automatic on quotation confirmation

3. **Cancel Reservation**
   - Initial State: Préréservé
   - Action: Click "Cancel Reservation" in modal
   - Result: Status returns to Disponible
   - System: Manual action via modal

## UI Elements

### Colors
- Disponible: Light Blue (badge-info)
- Préréservé: Red (badge-danger)
- Vendu: Green (badge-success)

### Counters
- Available Count = Disponible + Préréservé
- Sold Count = Vendu
- Pre-reserved Count = Préréservé

### Modal Actions
- Disponible: Shows "Create Quotation" button
- Préréservé: Shows "Cancel Reservation" button
- Vendu: No action buttons

## Technical Implementation

### Status Field
```python
apartment_state = fields.Selection([
    ('disponible', 'Disponible'),
    ('prereserved', 'Préréservé'),
    ('sold', 'Vendu'),
], string='Status', default='disponible')
```

### Computations
- Available count includes both disponible and prereserved states
- Pre-reserved count only includes prereserved state
- Sold count only includes sold state

### Automation
1. On quotation creation:
   ```python
   state = 'prereserved'
   is_locked = True
   locked_by_order_id = quotation.id
   ```

2. On quotation confirmation:
   ```python
   state = 'sold'
   ```

3. On reservation cancellation:
   ```python
   state = 'disponible'
   is_locked = False
   locked_by_order_id = False
   ```

## Testing Scenarios

1. **Basic Flow**
   - Create new apartment → Status: Disponible
   - Create quotation → Status: Préréservé
   - Confirm quotation → Status: Vendu

2. **Cancellation Flow**
   - Create new apartment → Status: Disponible
   - Create quotation → Status: Préréservé
   - Cancel reservation → Status: Disponible

3. **Counter Verification**
   - Create 3 apartments
   - Create quotation for 2 → Should show: 3 available (1 disponible + 2 préréservé)
   - Confirm 1 quotation → Should show: 2 available (1 disponible + 1 préréservé), 1 sold
   - Cancel 1 reservation → Should show: 2 available (2 disponible), 1 sold
