"""Mapping between admin roles and permissions."""

from __future__ import annotations

from typing import Iterable, Mapping, Set


# Global permissions
PERM_VIEW_READONLY = "admin.read"
PERM_MANAGE_USERS = "admin.users.manage"
PERM_MANAGE_ROLES = "admin.roles.manage"
PERM_MANAGE_SECURITY = "admin.security.manage"
PERM_VIEW_AUDIT = "admin.audit.view"

PERM_ACTION_EXTEND = "actions.extend_subscription"
PERM_ACTION_BALANCE = "actions.recharge_balance"
PERM_ACTION_BLOCK = "actions.block_user"
PERM_ACTION_SYNC = "actions.sync_access"


ROLE_PERMISSIONS: Mapping[str, Set[str]] = {
    "viewer": {
        PERM_VIEW_READONLY,
    },
    "manager": {
        PERM_VIEW_READONLY,
        PERM_VIEW_AUDIT,
        PERM_ACTION_EXTEND,
        PERM_ACTION_BALANCE,
        PERM_ACTION_SYNC,
    },
    "superadmin": {
        PERM_VIEW_READONLY,
        PERM_MANAGE_USERS,
        PERM_MANAGE_ROLES,
        PERM_MANAGE_SECURITY,
        PERM_VIEW_AUDIT,
        PERM_ACTION_EXTEND,
        PERM_ACTION_BALANCE,
        PERM_ACTION_BLOCK,
        PERM_ACTION_SYNC,
    },
}


def merge_permissions(role_slugs: Iterable[str]) -> Set[str]:
    """Collect permissions granted by the given roles."""
    perms: Set[str] = set()
    for slug in role_slugs:
        perms.update(ROLE_PERMISSIONS.get(slug, set()))
    return perms


def has_permission(permissions: Set[str], required: str) -> bool:
    """Check whether permission set contains required permission."""
    return required in permissions
