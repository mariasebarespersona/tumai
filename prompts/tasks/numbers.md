Numbers (R2B) – reglas mínimas

- Si intent == numbers.set_cell:
  - Validar address tipo A1 y value string/num.
  - Devolver JSON guía: {"action":"set_cell","cell":"B5","value":"1000","template_key":"R2B"}.
  - No calcular a mano: el backend hace el recálculo en cascada.
- Si intent == numbers.clear_cell:
  - Devolver {"action":"clear_cell","cell":"B7","template_key":"R2B"}.
- Si intent == numbers.export:
  - Devolver {"action":"export","template_key":"R2B"}.
- Si confidence < 0.75:
  - Devolver {"action":"clarify","question":"¿Confirmas escribir 1000 en B5?"}.


