-- Add helpful indexes for Numbers Table performance (idempotent)
create index if not exists idx_numbers_values_prop_tpl_addr
  on numbers_table_values(property_id, template_key, cell_address);

create index if not exists idx_numbers_templates_prop_tpl
  on numbers_templates(property_id, template_key);

