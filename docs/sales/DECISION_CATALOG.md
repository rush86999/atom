# Brennan Machinery — Sales Decision Catalog (draft)

> Auto-generated 2026-08-25 21:37 from 7 classified customer emails (of 7 scanned). Learn the business before automating it — review each row, correct the rules, and this becomes the agent's business-knowledge base.

| Situation (rule) | # | Action(s) | Human? | Systems | Exceptions | Examples |
|---|---|---|---|---|---|---|
| quote_request_followup | 1 | ask_human (1) | YES | inventory, price_list, zoho_crm | - | Brennan Machinery |
| standard accessory pricing request | 1 | draft_quote (1) | no | emails, price_list | - | Re: [EXT] Brennan Machinery |
| standard machine + stock available | 1 | draft_quote (1) | YES | price_list, zoho_inventory | - | Quote for machine model number |
| send_quote -> ? | 1 | ? (1) | no | - | - | Re: Quote for iron worker |
| standard_machine_quote_request | 1 | check_inventory (1) | no | price_list, vendor_portal, zoho_inventory | - | Heck notcher |
| credit_application_required_for_net30_terms | 1 | ask_human (1) | YES | emails, price_list, shipping, zoho_inventory | - | Re: Brennan Machinery |
| question -> provide_info | 1 | provide_info (1) | no | emails, price_list, shipping, zoho_inventory | - | RE: Brennan Machinery |
