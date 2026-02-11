"""
Factory for User model.
"""

import factory
from factory import fuzzy
from tests.factories import BaseFactory
from core.models import User, UserRole, UserStatus


class UserFactory(BaseFactory):
    """Factory for creating User instances."""

    class Meta:
        model = User

    # Required fields
    id = factory.Faker('uuid4')
    email = factory.Faker('email')
    password_hash = factory.Faker('password')  # In tests, use fake hash
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')

    # Role and status
    role = fuzzy.FuzzyChoice([r.value for r in UserRole])
    status = fuzzy.FuzzyChoice([s.value for s in UserStatus])

    # Optional fields
    specialty = factory.Faker('job')
    skills = factory.Faker('text', max_nb_chars=100)
    email_verified = fuzzy.FuzzyChoice([True, False])
    created_at = factory.Faker('date_time_this_year')

    # Onboarding
    onboarding_completed = fuzzy.FuzzyChoice([True, False])
    onboarding_step = factory.Faker('word')
    capacity_hours = fuzzy.FuzzyFloat(20.0, 60.0)
    hourly_cost_rate = fuzzy.FuzzyFloat(0.0, 200.0)


class AdminUserFactory(UserFactory):
    """Factory for admin users."""

    role = UserRole.SUPER_ADMIN.value


class MemberUserFactory(UserFactory):
    """Factory for regular members."""

    role = UserRole.MEMBER.value
    status = UserStatus.ACTIVE.value
