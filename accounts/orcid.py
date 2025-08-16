import logging

import jwt
import requests
from django.conf import settings
from django.contrib import auth, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from jwt.algorithms import RSAAlgorithm

User = get_user_model()
logger = logging.getLogger('authentication')


def get_best_email(orcid_record: dict) -> str | None:
    emails = orcid_record.get("person", {}).get("emails", {}).get("email", []) or []
    if not emails:
        return None

    # Keep only verified emails
    verified = [e for e in emails if e.get("verified")]
    if not verified:
        return None

    # Prefer the primary if it exists, else the first verified
    primary = next((e.get("email") for e in verified if e.get("primary")), None)
    return primary or verified[0].get("email")


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

    def authenticate(self, request, claims=None, record=None, **kwargs):
        """
        Authenticate or create user based on ORCiD OIDC claims.
        """
        if not record:
            logger.error("No record provided for ORCiD authentication.")
            return None
        else:
            logger.debug(f"Claims received: {claims}")
            logger.debug(f"ORCiD record received: {record}")

        # ORCiD is in 'sub' claim, a URI like https://orcid.org/0000-0002-1825-0097
        orcid_id = claims.get("sub")
        if not orcid_id:
            logger.error("ORCiD 'sub' claim missing.")
            return None

        # Extract ORCiD identifier string (last part of the URI)
        orcid_identifier = orcid_id.rsplit('/', 1)[-1]

        given_name = claims.get("given_name") or ""
        family_name = claims.get("family_name") or ""

        # Extract verified email(s)
        email = get_best_email(record) if record else None

        if not email:
            logger.warning(f"No verified email found for ORCiD user {orcid_identifier}")
            messages.error(request,
                           "No verified email found in ORCiD profile. You must have a verified email in your ORCiD profile to log in.")
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


def get_orcid_jwks():
    """Fetch ORCiD JWKS."""
    jwks_url = f"{settings.ORCID_BASE}/oauth/jwks"
    try:
        resp = requests.get(jwks_url)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch ORCiD JWKS: {e}")
        return None


def decode_orcid_id_token(id_token):
    """Verify ID token signature and return claims."""
    jwks = get_orcid_jwks()
    if not jwks:
        return None

    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    if not kid:
        logger.error("ID token missing 'kid' header")
        return None

    key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if not key_data:
        logger.error("No matching JWK for token")
        return None

    public_key = RSAAlgorithm.from_jwk(key_data)
    try:
        claims = jwt.decode(
            id_token,
            key=public_key,
            algorithms=["RS256"],
            audience=settings.ORCID_CLIENT_ID,
        )
        return claims
    except jwt.PyJWTError as e:
        logger.error(f"Failed to verify ID token: {e}")
        return None


def orcid_callback(request):
    logger.debug("Full request URL: %s", request.build_absolute_uri())
    logger.debug("GET params: %s", request.GET)

    # Fetch but do not immediately remove state/nonce
    session_state = request.session.get("oidc_state")
    session_nonce = request.session.get("oidc_nonce")

    state = request.GET.get("state")
    if not state:
        logger.error("Missing state parameter in ORCiD callback.")
        return redirect("accounts:login")
    if state != session_state:
        logger.error(
            "State mismatch. Possible CSRF attack. "
            f"Session: {session_state}, Callback: {state}"
        )
        return redirect("accounts:login")

    # Now safe to pop them to prevent reuse
    request.session.pop("oidc_state", None)
    request.session.pop("oidc_nonce", None)

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
        "redirect_uri": request.build_absolute_uri(reverse("orcid-callback")),
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

    # Verify ID token
    claims = decode_orcid_id_token(id_token)
    if not claims:
        return redirect("accounts:login")

    # Check nonce
    if claims.get("nonce") != session_nonce:
        logger.error("Nonce mismatch. Possible replay attack.")
        return redirect("accounts:login")

    # --- Fetch full ORCID record (member API) ---
    record = {}
    orcid_id = claims.get("sub")
    if orcid_id:
        api_base = settings.ORCID_BASE.replace("//", "//api.")  # e.g. sandbox → api.sandbox
        record_url = f"{api_base}/v3.0/{orcid_id}"
        try:
            record_response = requests.get(
                record_url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            )
            record_response.raise_for_status()
            record = record_response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch ORCID full record: {e}")

    combined_info = {
        "claims": claims,
        "record": record,
    }

    # Authenticate via backend with verified claims
    user = auth.authenticate(request, **combined_info)
    if user:
        auth.login(request, user)
        if request.session.get("just_created_account", False):
            return redirect("profile")
        return redirect("home")

    logger.error("ORCID authentication failed.")
    return redirect("accounts:login")
