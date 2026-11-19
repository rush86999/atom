"""Internal persistence for local invoice -> provider invoice bindings.

This module deliberately does not authenticate the caller, decrypt credentials,
call a provider, change invoice business status, or claim that a payment
settled.  The caller must prove authority and provider identity first; this
service only records the resulting binding and its audit receipts.

Before any write, the service resolves the exact active ``UserConnection`` row
for the supplied connection, actor, workspace, workspace tenant, and provider
integration by reading the existing model.  The scoped connection lookup never
decrypts credentials and never calls a provider.

The write contract is:

* The first binding inserts the current row at revision 1 and appends receipt 1.
* A correction is an optimistic compare-and-swap on ``expected_revision`` and
  appends the next receipt in the same savepoint.
* Any conflict rolls back the savepoint, so a failed attempt cannot leave a
  binding change or a misleading receipt behind.
* Repeating an already-applied identical binding is a no-op and does not append
  another receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .models import (
    Invoice,
    InvoiceProviderBinding,
    InvoiceProviderBindingRevision,
)


class InvoiceProviderBindingError(Exception):
    """Base error for the binding service."""


class InvoiceProviderBindingInvoiceNotFound(InvoiceProviderBindingError, LookupError):
    """The local invoice does not exist in exactly the supplied workspace."""


class InvoiceProviderBindingConnectionNotFound(InvoiceProviderBindingError, LookupError):
    """No active connection matches the supplied binding scope."""


class InvoiceProviderBindingConflict(InvoiceProviderBindingError, ValueError):
    """The expected revision or external invoice uniqueness check failed."""

    def __init__(
        self,
        message: str,
        *,
        expected_revision: Optional[int] = None,
        current_revision: Optional[int] = None,
        binding_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        self.binding_id = binding_id


@dataclass(frozen=True)
class ProviderInvoiceIdentity:
    """The exact provider-side identity stored on a binding and its receipt."""

    provider: str
    provider_account_id: str
    provider_mode: str
    external_invoice_id: str
    connection_id: str


class _CompareAndSwapFailed(Exception):
    pass


def _required_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _identity_from_binding(binding: InvoiceProviderBinding) -> ProviderInvoiceIdentity:
    return ProviderInvoiceIdentity(
        provider=binding.provider,
        provider_account_id=binding.provider_account_id,
        provider_mode=binding.provider_mode,
        external_invoice_id=binding.external_invoice_id,
        connection_id=binding.connection_id,
    )


def _identity_matches(
    binding: InvoiceProviderBinding,
    identity: ProviderInvoiceIdentity,
) -> bool:
    return _identity_from_binding(binding) == identity


def _require_scoped_connection(
    session: Any,
    *,
    connection_id: str,
    actor_id: str,
    workspace_id: str,
    provider: str,
) -> None:
    """Require the exact active connection row before any binding write."""

    # Imported lazily so this service does not force core model import order.
    from core.models import UserConnection, Workspace

    workspace = session.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    ).scalar_one_or_none()
    if workspace is None:
        raise InvoiceProviderBindingConnectionNotFound(
            "active connection does not match the supplied workspace"
        )

    connection = session.execute(
        select(UserConnection).where(
            UserConnection.id == connection_id,
            UserConnection.user_id == actor_id,
            UserConnection.workspace_id == workspace_id,
            UserConnection.tenant_id == workspace.tenant_id,
            UserConnection.integration_id == provider,
            UserConnection.status == "active",
        )
    ).scalar_one_or_none()
    if connection is None:
        raise InvoiceProviderBindingConnectionNotFound(
            "active connection does not match the supplied user, workspace, "
            "tenant, and provider"
        )


def _find_binding(
    session: Any,
    *,
    workspace_id: str,
    invoice_id: str,
    provider: str,
) -> Optional[InvoiceProviderBinding]:
    return session.execute(
        select(InvoiceProviderBinding).where(
            InvoiceProviderBinding.workspace_id == workspace_id,
            InvoiceProviderBinding.invoice_id == invoice_id,
            InvoiceProviderBinding.provider == provider,
        )
    ).scalar_one_or_none()


def _ensure_sqlite_transaction(session: Any) -> None:
    """Ensure SQLite has a physical transaction before writing in a savepoint.

    Python's sqlite3 driver in legacy transaction mode does not begin a
    transaction for SELECT.  Releasing a savepoint before any write would then
    commit on release instead of remaining under the caller's transaction.
    """
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return

    connection = session.connection()
    driver_connection = getattr(connection, "driver_connection", None)
    if driver_connection is None:
        raw_connection = connection.connection
        driver_connection = getattr(
            raw_connection, "driver_connection", raw_connection
        )
    if not getattr(driver_connection, "in_transaction", False):
        connection.exec_driver_sql("BEGIN")


def _append_receipt(
    session: Any,
    *,
    binding: InvoiceProviderBinding,
    prior: Optional[ProviderInvoiceIdentity],
    new: ProviderInvoiceIdentity,
    actor_id: str,
    reason: Optional[str],
) -> InvoiceProviderBindingRevision:
    receipt = InvoiceProviderBindingRevision(
        binding_id=binding.id,
        workspace_id=binding.workspace_id,
        invoice_id=binding.invoice_id,
        revision=binding.revision,
        actor_id=actor_id,
        reason=reason,
        prior_provider=prior.provider if prior else None,
        prior_provider_account_id=prior.provider_account_id if prior else None,
        prior_provider_mode=prior.provider_mode if prior else None,
        prior_external_invoice_id=prior.external_invoice_id if prior else None,
        prior_connection_id=prior.connection_id if prior else None,
        new_provider=new.provider,
        new_provider_account_id=new.provider_account_id,
        new_provider_mode=new.provider_mode,
        new_external_invoice_id=new.external_invoice_id,
        new_connection_id=new.connection_id,
    )
    session.add(receipt)
    return receipt


def bind_invoice_to_provider(
    session: Any,
    *,
    invoice_id: str,
    workspace_id: str,
    provider: str,
    provider_account_id: str,
    provider_mode: str,
    external_invoice_id: str,
    connection_id: str,
    actor_id: str,
    reason: Optional[str] = None,
    expected_revision: Optional[int] = None,
) -> InvoiceProviderBinding:
    """Create or correct the current binding for a local invoice/provider.

    ``expected_revision`` is ``None`` (or ``0``) for the first insert, and the
    current binding revision for a correction.  The local invoice is looked up
    by the exact ``(invoice_id, workspace_id)`` database key; invoice metadata
    is never trusted for scoping.

    The supplied ``connection_id`` must identify an active ``UserConnection``
    owned by ``actor_id`` in the same workspace and tenant, for the same
    ``provider`` integration.  That row is resolved before any write.

    The caller owns the transaction.  Receipts are appended with ``flush()`` in
    the same transaction/savepoint, never with a separate commit.
    """

    if actor_id is not None and not isinstance(actor_id, str) and hasattr(actor_id, "id"):
        actor_id = actor_id.id

    invoice_id = _required_text("invoice_id", invoice_id)
    workspace_id = _required_text("workspace_id", workspace_id)
    provider = _required_text("provider", provider)
    provider_account_id = _required_text(
        "provider_account_id",
        provider_account_id,
    )
    provider_mode = _required_text("provider_mode", provider_mode)
    external_invoice_id = _required_text(
        "external_invoice_id",
        external_invoice_id,
    )
    connection_id = _required_text("connection_id", connection_id)
    actor_id = _required_text("actor_id", actor_id)

    if expected_revision is not None:
        if (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ValueError("expected_revision must be a non-negative integer or None")

    # Scope is established from the database row, never from invoice metadata.
    invoice = session.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise InvoiceProviderBindingInvoiceNotFound(
            "invoice does not exist in the supplied workspace"
        )

    # The connection is part of the binding scope: reject a connection from a
    # foreign actor, workspace, tenant, provider integration, or inactive row
    # before touching the binding or receipt tables.
    _require_scoped_connection(
        session,
        connection_id=connection_id,
        actor_id=actor_id,
        workspace_id=invoice.workspace_id,
        provider=provider,
    )

    identity = ProviderInvoiceIdentity(
        provider=provider,
        provider_account_id=provider_account_id,
        provider_mode=provider_mode,
        external_invoice_id=external_invoice_id,
        connection_id=connection_id,
    )

    existing = _find_binding(
        session,
        workspace_id=invoice.workspace_id,
        invoice_id=invoice.id,
        provider=provider,
    )

    if existing is None:
        if expected_revision not in (None, 0):
            raise InvoiceProviderBindingConflict(
                "cannot create a binding at a non-zero expected revision",
                expected_revision=expected_revision,
                current_revision=None,
            )

        try:
            _ensure_sqlite_transaction(session)
            with session.begin_nested():
                binding = InvoiceProviderBinding(
                    workspace_id=invoice.workspace_id,
                    invoice_id=invoice.id,
                    provider=identity.provider,
                    provider_account_id=identity.provider_account_id,
                    provider_mode=identity.provider_mode,
                    external_invoice_id=identity.external_invoice_id,
                    connection_id=identity.connection_id,
                    revision=1,
                )
                session.add(binding)
                session.flush()

                _append_receipt(
                    session,
                    binding=binding,
                    prior=None,
                    new=identity,
                    actor_id=actor_id,
                    reason=reason,
                )
                session.flush()
            return binding
        except IntegrityError as exc:
            # The savepoint rolled back both the binding and its receipt.  A
            # concurrent/repeated identical insert is safe to return as-is; any
            # other uniqueness failure is a real conflict.
            existing = _find_binding(
                session,
                workspace_id=invoice.workspace_id,
                invoice_id=invoice.id,
                provider=provider,
            )
            if existing is not None and _identity_matches(existing, identity):
                return existing
            raise InvoiceProviderBindingConflict(
                "external provider invoice is already bound in this workspace",
                expected_revision=expected_revision,
                current_revision=(
                    existing.revision if existing is not None else None
                ),
                binding_id=existing.id if existing is not None else None,
            ) from exc

    if expected_revision is None:
        # An exact repeat of an already-applied binding is a no-op.  It must
        # not append a receipt that implies another change occurred.
        if _identity_matches(existing, identity):
            return existing
        raise InvoiceProviderBindingConflict(
            "binding already exists at revision "
            f"{existing.revision}; supply expected_revision to correct it",
            expected_revision=expected_revision,
            current_revision=existing.revision,
            binding_id=existing.id,
        )

    if expected_revision != existing.revision:
        raise InvoiceProviderBindingConflict(
            f"binding revision changed: expected {expected_revision}, "
            f"found {existing.revision}",
            expected_revision=expected_revision,
            current_revision=existing.revision,
            binding_id=existing.id,
        )

    if _identity_matches(existing, identity):
        return existing

    prior = _identity_from_binding(existing)
    target_revision = expected_revision + 1

    try:
        _ensure_sqlite_transaction(session)
        with session.begin_nested():
            result = session.execute(
                update(InvoiceProviderBinding)
                .where(
                    InvoiceProviderBinding.id == existing.id,
                    InvoiceProviderBinding.revision == expected_revision,
                )
                .values(
                    provider_account_id=identity.provider_account_id,
                    provider_mode=identity.provider_mode,
                    external_invoice_id=identity.external_invoice_id,
                    connection_id=identity.connection_id,
                    revision=target_revision,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise _CompareAndSwapFailed

            session.refresh(existing)
            _append_receipt(
                session,
                binding=existing,
                prior=prior,
                new=identity,
                actor_id=actor_id,
                reason=reason,
            )
            session.flush()
    except _CompareAndSwapFailed:
        current_revision = session.execute(
            select(InvoiceProviderBinding.revision).where(
                InvoiceProviderBinding.id == existing.id
            )
        ).scalar_one_or_none()
        raise InvoiceProviderBindingConflict(
            "binding revision changed while correcting it",
            expected_revision=expected_revision,
            current_revision=current_revision,
            binding_id=existing.id,
        ) from None
    except IntegrityError as exc:
        # The savepoint rolled back the update and receipt together.
        session.expire(existing)
        raise InvoiceProviderBindingConflict(
            "external provider invoice is already bound in this workspace",
            expected_revision=expected_revision,
            current_revision=expected_revision,
            binding_id=existing.id,
        ) from exc

    return existing
