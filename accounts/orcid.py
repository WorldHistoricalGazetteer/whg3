import logging

import jwt
import requests
from django.conf import settings
from django.contrib import auth, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.db import transaction
from django.shortcuts import redirect

User = get_user_model()
logger = logging.getLogger('authentication')


class OIDCBackend(BaseBackend):
    """
    Custom authentication backend to authenticate users via ORCiD OpenID Connect.

    Expects ORCiD claims including:
    - 'sub': the ORCiD iD URI (e.g. https://orcid.org/0000-0002-1825-0097)
    - 'name': user's full name
    - 'given_name', 'family_name' (optional)
    - 'emails': list of emails with 'value' and 'verified' flags
    - 'affiliation' or 'employments' (may be nested - you can extend to parse)
    """

    def authenticate(self, request, id_token=None, userinfo=None, **kwargs):
        """
        Authenticate or create user based on ORCiD OIDC claims.
        """

        if not id_token and not userinfo:
            logger.warning("No id_token or userinfo provided for ORCiD authentication.")
            return None

        logger.debug("Received id_token: %s", id_token)
        logger.debug("Received userinfo: %s", userinfo)

        # Prefer userinfo dict, fallback to decoded id_token claims
        claims = userinfo or id_token

        # ORCiD iD is usually in 'sub' claim, a URI like https://orcid.org/0000-0002-1825-0097
        orcid_id = claims.get("sub")
        if not orcid_id:
            logger.error("ORCiD 'sub' claim missing.")
            return None

        # Extract ORCiD identifier string (last part of the URI)
        orcid_identifier = orcid_id.rsplit('/', 1)[-1]

        # Extract name fields
        given_name = claims.get("given_name") or ""
        family_name = claims.get("family_name") or ""

        # Extract verified email(s)
        email = None
        emails = claims.get("emails") or []
        # ORCiD returns a list of emails with 'value' and 'verified' flags
        for e in emails:
            if e.get("verified") and e.get("value"):
                email = e["value"]
                break

        # As fallback, try 'email' claim if it exists and is verified
        if not email and claims.get("email") and claims.get("email_verified"):
            email = claims["email"]

        if not email:
            logger.warning(f"No verified email found for ORCiD user {orcid_identifier}")
            messages.error(request, "No verified email found in ORCiD profile. You must have a verified email in your ORCiD profile to log in.")
            return None

        try:
            user = User.objects.get(orcid=orcid_id)
            created = False
        except User.DoesNotExist:
            user = User(orcid=orcid_id, username=orcid_identifier)
            created = True

        # Update user info fields
        user.email = email or ""
        user.given_name = given_name or ""
        user.surname = family_name or ""
        user.username = user.username or orcid_identifier

        # Save user
        with transaction.atomic():
            # Note: users.signals.py.welcome_email is triggered here if user is newly-created
            user.save()

        # Store ORCiD ID in session
        if request is not None:
            request.session["orcid_id"] = orcid_id
            request.session["orcid_given_name"] = user.given_name
            if created:
                request.session["just_created_account"] = True

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


def orcid_callback(request):
    # Remove 'state' and 'nonce' from session immediately to prevent reuse
    session_state = request.session.pop("oidc_state", None)
    session_nonce = request.session.pop("oidc_nonce", None)

    # Validate state parameter
    state = request.GET.get("state")
    if not state or state != session_state:
        logger.error("Invalid state parameter. Possible CSRF attack.")
        return redirect("accounts:login")

    code = request.GET.get("code")
    if not code:
        logger.error("No authorization code provided by ORCiD.")
        return redirect("accounts:login")

    token_url = f"{settings.ORCID_BASE}/oauth/token"
    data = {
        "client_id": settings.ORCID_CLIENT_ID,
        "client_secret": settings.ORCID_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": request.build_absolute_uri("/orcid-callback/"),
    }
    headers = {"Accept": "application/json"}

    try:
        token_response = requests.post(token_url, data=data, headers=headers)
        token_response.raise_for_status()
        token_json = token_response.json()
    except requests.RequestException as e:
        logger.error(f"Token request failed: {e}")
        return redirect("accounts:login")

    # Required tokens
    id_token = token_json.get("id_token")
    access_token = token_json.get("access_token")
    if not id_token or not access_token:
        logger.error(f"ORCID did not return expected tokens: {token_json}")
        return redirect("accounts:login")

    # Verify nonce inside ID token
    try:
        claims = jwt.decode(id_token, options={"verify_signature": False})
    except jwt.DecodeError:
        logger.error("Invalid ID token received from ORCID.")
        return redirect("accounts:login")

    if claims.get("nonce") != session_nonce:
        logger.error("Nonce mismatch. Possible replay attack.")
        return redirect("accounts:login")

    # Get userinfo (optional, since ID token already has claims)
    try:
        userinfo_response = requests.get(
            f"{settings.ORCID_BASE}/oauth/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch user info: {e}")
        return redirect("accounts:login")

    # Authenticate user via custom backend
    user = auth.authenticate(request, id_token=id_token, userinfo=userinfo)
    if user:
        auth.login(request, user)
        if request.session.get("just_created_account", False):
            return redirect("profile")
        return redirect("home")

    logger.error("ORCID authentication failed.")
    return redirect("accounts:login")