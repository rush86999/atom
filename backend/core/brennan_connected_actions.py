"""Compatibility shim for the former reference-deployment module name.

The capability implementations live in :mod:`core.connected_actions`; new
plans use the business-independent ``connected.*`` action names.  This module
keeps existing imports working while the reference campaign is retired.
"""
from core.connected_actions import *  # noqa: F401,F403
from core.connected_actions import (  # noqa: F401
    action_executor_outcome,
    books_create_bill,
    books_create_estimate,
    books_get_bill,
    books_get_estimate,
    books_list_accounts,
    books_propose_bill,
    books_resolve_vendor,
    crm_get_record,
    crm_search_records,
    inventory_check_stock,
    inventory_get_item,
    knowledge_sync_status,
    onedrive_list_page,
    onedrive_read_file,
    onedrive_sync_page,
    outlook_create_draft,
    outlook_read_attachments,
    workdrive_list_page,
    workdrive_read_file,
    workdrive_sync_page,
)
