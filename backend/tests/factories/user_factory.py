"""
Factory for User model.
"""

import factory
from factory import fuzzy
from tests.factories.base import BaseFactory
from core.models import User, UserRole, UserStatus


class UserFactory(BaseFactory):
    """Factory for creating User instances."""

    class Meta:
        model = User

    # Required fields
    id = factory.Faker('uuid4')
    email = factory.Faker('email')
    hashed_password = factory.Faker('password')  # In tests, use fake hash
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')

    # Role and status
    role = fuzzy.FuzzyChoice([r.value for r in UserRole])
    status = fuzzy.FuzzyChoice([s.value for s in UserStatus])

    # Optional fields (only those that exist in User model)
    created_at = factory.Faker('date_time_this_year')


class AdminUserFactory(UserFactory):
    """Factory for admin users."""

    role = UserRole.SUPER_ADMIN.value


class MemberUserFactory(UserFactory):
    """Factory for regular members."""

    role = UserRole.MEMBER.value
    status = UserStatus.ACTIVE.value
