# accounts.orcid.py

from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class OIDCBackend(OIDCAuthenticationBackend):
    def create_user(self, claims):
        orcid_id = claims.get("sub")
        name = claims.get("name", "")
        email = claims.get("email", None)

        return User.objects.create_user(
            username=orcid_id,
            first_name=name.split(" ")[0] if name else "",
            last_name=" ".join(name.split(" ")[1:]) if name else "",
            email=email or "",
            password=None  # No password for ORCiD accounts
        )

    def filter_users_by_claims(self, claims):
        orcid_id = claims.get("sub")
        return User.objects.filter(username=orcid_id)

    def update_user(self, user, claims):
        """Optional: update fields on every login."""
        return user
