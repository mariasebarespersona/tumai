Documentos/Email – reglas mínimas

- Si intent == docs.send_email:
  - Requiere confirmación: {"action":"confirm_send","to":"...", "subject":"..."}.
  - No mostrar HTML en chat; solo confirmación breve tras enviar.
- Si intent == docs.list:
  - Llama a list_docs y resume subidos vs pendientes.
- Si intent == docs.upload:
  - Proponer slot y pedir confirmación antes de subir.
- Si confidence < 0.75:
  - {"action":"clarify","question":"¿Quieres enviar por email el documento X?"}.


