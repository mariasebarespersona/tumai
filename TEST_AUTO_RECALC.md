# Test Plan: Auto-Recalculate Debug

## Check Browser Console

Open Developer Tools (F12) and look for these logs:

### Expected logs when opening a template:
```
[Numbers Table] Auto-loading triggered: {shouldLoad: true, ...}
[Numbers Table] loadAddresses complete, calling autoRecalculateFormulas...
[Numbers Table] 🔄 Auto-recalculating formulas...
[Numbers Table] ✅ Formulas recalculated: {D5: 10, E5: 110, ...}
```

### If you DON'T see these logs:
1. The useEffect might not be triggering
2. propertyId or excelTemplate might be null
3. There might be a JS error

### If you see "No formulas to calculate":
1. The structure might not have formulas defined
2. The current_values might be empty
3. Dependencies might not be resolved

## Manual Test

In browser console, run:
```javascript
// Check if values exist
fetch('http://localhost:7901/api/numbers/table-values?property_id=<YOUR_PROPERTY_ID>&template_key=R2B')
  .then(r => r.json())
  .then(console.log)

// Manually trigger recalculate
const form = new FormData()
form.append('property_id', '<YOUR_PROPERTY_ID>')
form.append('template_key', 'R2B')
fetch('http://localhost:7901/api/numbers/recalculate', {method: 'POST', body: form})
  .then(r => r.json())
  .then(console.log)
```

## Backend Logs

Check backend terminal for:
```
[recalculate_all_formulas] Starting full recalculation...
[recalculate_all_formulas] Found X cells with formulas
[recalculate_all_formulas] Found Y cells with values: ['B5', 'C5', ...]
[recalculate_all_formulas] Successfully calculated Z formulas
```

## Common Issues

### Issue 1: Dependencies not resolved
- **Symptom**: Backend says "No formulas to calculate"
- **Cause**: Formula references cells that don't have values yet
- **Solution**: Check that B5 and C5 actually have values in the database

### Issue 2: Structure has no formulas
- **Symptom**: Backend says "Found 0 cells with formulas"
- **Cause**: Excel wasn't imported with formulas, or formulas weren't saved
- **Solution**: Re-import the Excel file, ensure formulas are preserved

### Issue 3: Frontend not calling the endpoint
- **Symptom**: No logs in browser console about recalculating
- **Cause**: useEffect dependencies or async/await issue
- **Solution**: Check dependencies and error handling

### Issue 4: Infinite loop
- **Symptom**: Page keeps reloading or freezing
- **Cause**: useEffect dependencies causing re-renders
- **Solution**: Remove addressesData from dependencies

