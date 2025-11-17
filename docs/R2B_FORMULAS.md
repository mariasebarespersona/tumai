# R2B Excel Formulas Reference

This document identifies all formulas needed for the R2B Numbers Table template. Yellow cells are user inputs, all other cells should contain formulas.

## Column Structure
- **Column A**: Row labels (text)
- **Column B**: Importe (€) - Amount in euros
- **Column C**: IVA (%) - VAT percentage
- **Column D**: IVA (€) - VAT amount in euros
- **Column E**: Total (IVA incl.) - Total including VAT

---

## Section 1: Bº RAMA (Rows 3-15)

### Row 4: Headers
- **B4**: "Importe (€)" (text)
- **C4**: "IVA (%)" (text)
- **D4**: "IVA (€)" (text)
- **E4**: "Total (IVA incl.)" (text)

### Row 5: Total pagado
- **B5**: User input (yellow) - Total paid amount
- **C5**: User input (yellow) - VAT percentage
- **D5**: `=B5*C5/100` - Calculate VAT amount: Importe × IVA% / 100
- **E5**: `=B5+D5` - Total with VAT: Importe + IVA (€)

### Row 6: Precio de venta
- **B6**: User input (yellow) - Sale price
- **C6**: User input (yellow) - VAT percentage
- **D6**: `=B6*C6/100` - Calculate VAT amount
- **E6**: `=B6+D6` - Total with VAT

### Row 7: Terreno urbano
- **B7**: User input (yellow) - Urban land cost
- **C7**: User input (yellow) - VAT percentage
- **D7**: `=B7*C7/100` - Calculate VAT amount
- **E7**: `=B7+D7` - Total with VAT

### Row 8: Terreno rústico
- **B8**: User input (yellow) - Rural land cost
- **C8**: User input (yellow) - VAT percentage (or 0 if not applicable)
- **D8**: `=IF(C8>0, B8*C8/100, 0)` or `=B8*C8/100` - Calculate VAT amount (0 if no VAT)
- **E8**: `=B8+D8` - Total with VAT

### Row 9: Empty row (separator)

### Row 10: Bº bruto venta terrenos
- **B10**: `=B6-B7-B8` - Gross profit from land sale: Precio de venta - Terreno urbano - Terreno rústico
- **C10**: Empty (no VAT calculation for profit)
- **D10**: Empty
- **E10**: Empty

### Row 11: Project Mgmt fees
- **B11**: User input (yellow) - Project management fees
- **C11**: Empty (typically no VAT on fees)
- **D11**: Empty
- **E11**: Empty

### Row 12: Total ingresos brutos (€)
- **B12**: `=B10+B11` - Total gross income: Bº bruto + Project Mgmt fees
- **C12**: Empty
- **D12**: Empty
- **E12**: Empty

### Row 13: Impuestos (25%)
- **B13**: `=B12*0.25` - Taxes at 25%: Total ingresos brutos × 25%
- **C13**: "25%" (text label, or could be user input if variable)
- **D13**: Empty
- **E13**: Empty

### Row 14: Impuestos (€)
- **B14**: `=B13` - Same as B13 (taxes in euros)
- **C14**: Empty
- **D14**: Empty
- **E14**: Empty

### Row 15: Bº neto (€)
- **B15**: `=B12-B14` - Net profit: Total ingresos brutos - Impuestos (€)
- **C15**: Empty
- **D15**: Empty
- **E15**: Empty

---

## Section 2: AUTOPROMOCIÓN (Rows 17-22)

### Row 17: Section title "AUTOPROMOCIÓN" (text)

### Row 18: Total Bº Neto RAMA (€)
- **B18**: `=B15` - Reference to Bº neto from Bº RAMA section
- **C18**: Empty
- **D18**: Empty
- **E18**: Empty

### Row 19: Ingresos upfront
- **B19**: User input (yellow) - Upfront income
- **C19**: Empty
- **D19**: Empty
- **E19**: Empty

### Row 20: Ingresos durante construcción
- **B20**: User input (yellow) - Income during construction
- **C20**: Empty
- **D20**: Empty
- **E20**: Empty

### Row 21: Ingresos al final de construcción
- **B21**: User input (yellow) - Income at end of construction
- **C21**: Empty
- **D21**: Empty
- **E21**: Empty

### Row 22: SIN RIESGO CONSTRUCCIÓN (text label)

---

## Section 3: Coste comprador (Rows 24-29)

### Row 24: Section title "Coste comprador" (text)

### Row 25: Terrenos
- **B25**: User input (yellow) - Land cost
- **C25**: Empty
- **D25**: Empty
- **E25**: Empty

### Row 26: Project Management
- **B26**: User input (yellow) - Project management cost
- **C26**: Empty
- **D26**: Empty
- **E26**: Empty

### Row 27: Acometidas
- **B27**: User input (yellow) - Utilities/connections cost
- **C27**: Empty
- **D27**: Empty
- **E27**: Empty

### Row 28: Costes de construcción
- **B28**: User input (yellow) - Construction costs
- **C28**: Empty
- **D28**: Empty
- **E28**: Empty

### Row 29: Total Coste Comprador
- **B29**: `=B25+B26+B27+B28` - Sum of all buyer costs: Terrenos + Project Management + Acometidas + Costes de construcción
- **C29**: Empty
- **D29**: Empty
- **E29**: Empty

---

## Summary of Formulas by Cell

### IVA Calculations (Column D):
- **D5**: `=B5*C5/100`
- **D6**: `=B6*C6/100`
- **D7**: `=B7*C7/100`
- **D8**: `=IF(C8>0, B8*C8/100, 0)` or `=B8*C8/100`

### Total with VAT (Column E):
- **E5**: `=B5+D5`
- **E6**: `=B6+D6`
- **E7**: `=B7+D7`
- **E8**: `=B8+D8`

### Profit Calculations:
- **B10**: `=B6-B7-B8` (Gross profit from land sale)
- **B12**: `=B10+B11` (Total gross income)
- **B13**: `=B12*0.25` (Taxes at 25%)
- **B14**: `=B13` (Taxes in euros)
- **B15**: `=B12-B14` (Net profit)

### AUTOPROMOCIÓN:
- **B18**: `=B15` (Reference to net profit)

### Coste Comprador Total:
- **B29**: `=B25+B26+B27+B28` (Sum of all buyer costs)

---

## Notes

1. **Empty cells**: Rows 2, 9, 16, 23, 30 are separators and should remain empty
2. **Text cells**: Headers, labels, and section titles are text (not formulas)
3. **User inputs (yellow)**: All yellow cells are user inputs and should NOT have formulas
4. **Formula cells**: All non-yellow, non-empty cells in columns B, D, E should have formulas
5. **Column C**: Mostly user inputs (IVA percentages), except C13 which might be "25%" text or a formula reference

## Implementation Notes

When importing the Excel template:
1. Preserve all formulas that start with `=`
2. Mark yellow cells as user inputs (no formulas)
3. Ensure formulas reference correct cell addresses (B6, B7, etc.)
4. Handle empty cells appropriately (don't create formulas for separators)

