# -*- coding: utf-8 -*-
"""OIDC (OpenID Connect) authentication endpoints.

This module provides endpoints for OAuth2/OpenID Connect authentication 
flows, supporting integration with providers like Keycloak, Auth0, Google, etc.

Features:
- Standard OIDC authorization code flow
- Multiple OIDC provider support
- Automatic user provisioning
- Token validation and caching
- Secure state management
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode, urljoin, parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from ..auth import create_token, verify_token
from ...db import SessionLocal, UserRepository
from ...constant import (
    OIDC_PROVIDERS,
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
    OIDC_ISSUER_URL,
    OIDC_AUTHORIZATION_ENDPOINT,
    OIDC_TOKEN_ENDPOINT,
    OIDC_USERINFO_ENDPOINT,
    OIDC_REDIRECT_URI,
    OIDC_SCOPES,
    OIDC_CALLBACK_PATH,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oidc", tags=["oidc"])

# In-memory state store for OIDC flows (in production, use Redis)
# Maps state parameter to OIDC provider and any additional context
_oidc_state_store = {}

# Cache for OIDC provider configurations
_oidc_provider_cache = {}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class OIDCProviderInfo(BaseModel):
    """Information about an OIDC provider."""
    id: str
    name: str
    enabled: bool
    issuer_url: Optional[str] = None
    authorization_endpoint: Optional[str] = None
    discovery_url: Optional[str] = None


class OIDCProvidersResponse(BaseModel):
    """Response containing available OIDC providers."""
    providers: List[OIDCProviderInfo]


class OIDCLoginRequest(BaseModel):
    """Request to initiate OIDC login."""
    provider_id: str
    redirect_url: Optional[str] = None


class OIDCCallbackResponse(BaseModel):
    """Response from OIDC callback."""
    token: str
    username: str
    user_id: Optional[int] = None
    role: str = "user"
    provider: str


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_oidc_client(provider_id: str = "default"):
    """Get Authlib OIDC client for a specific provider.
    
    Args:
        provider_id: Provider ID ("default" or from OIDC_PROVIDERS config)
    
    Returns:
        OAuth client or None if not configured
    """
    try:
        from authlib.integrations.starlette_client import OAuth
        from authlib.oidc.core import UserInfo
    except ImportError:
        logger.error("Authlib is not installed. OIDC support requires authlib>=1.3.0")
        return None
    
    # Check if provider exists in cache
    cache_key = f"oidc_client:{provider_id}"
    if cache_key in _oidc_provider_cache:
        return _oidc_provider_cache[cache_key]
    
    # Create OAuth client
    oauth = OAuth()
    
    # Determine which provider to configure
    provider_config = None
    
    if provider_id == "default":
        # Configure from environment variables
        if not OIDC_CLIENT_ID or not OIDC_CLIENT_SECRET or not OIDC_ISSUER_URL:
            logger.warning("OIDC environment variables not configured for default provider")
            return None
        
        # Configure provider
        provider_config = {
            "client_id": OIDC_CLIENT_ID,
            "client_secret": OIDC_CLIENT_SECRET,
            "issuer_url": OIDC_ISSUER_URL,
            "scopes": OIDC_SCOPES or 'openid email profile',
        }
    else:
        # Find provider in OIDC_PROVIDERS
        for provider in OIDC_PROVIDERS:
            if provider.get("id") == provider_id and provider.get("enabled", False):
                provider_config = provider
                break
        
        if not provider_config:
            logger.warning(f"OIDC provider '{provider_id}' not found or not enabled")
            return None
    
    # Configure provider with appropriate name
    provider_name = f"coco_{provider_id}"
    
    # Use server metadata URL for discovery if available
    server_metadata_url = None
    if provider_config.get("discovery_url"):
        server_metadata_url = provider_config["discovery_url"]
    elif provider_config.get("issuer_url"):
        server_metadata_url = provider_config["issuer_url"].rstrip('/') + '/.well-known/openid-configuration'
    
    oauth.register(
        name=provider_name,
        client_id=provider_config["client_id"],
        client_secret=provider_config["client_secret"],
        server_metadata_url=server_metadata_url,
        client_kwargs={
            'scope': provider_config.get("scopes", OIDC_SCOPES or 'openid email profile'),
            'prompt': 'login',
        }
    )
    
    # Cache the client
    _oidc_provider_cache[cache_key] = oauth
    
    return oauth


def _get_oidc_providers() -> List[OIDCProviderInfo]:
    """Get list of configured OIDC providers."""
    providers = []
    
    # Add provider from environment variables if configured
    if OIDC_CLIENT_ID and OIDC_CLIENT_SECRET and OIDC_ISSUER_URL:
        providers.append(OIDCProviderInfo(
            id="default",
            name="OIDC Provider",
            enabled=True,
            issuer_url=OIDC_ISSUER_URL,
            authorization_endpoint=OIDC_AUTHORIZATION_ENDPOINT,
            discovery_url=OIDC_ISSUER_URL.rstrip('/') + '/.well-known/openid-configuration',
        ))
    
    # Add providers from OIDC_PROVIDERS config (if available)
    if OIDC_PROVIDERS:
        for provider_config in OIDC_PROVIDERS:
            providers.append(OIDCProviderInfo(
                id=provider_config.get("id", "unknown"),
                name=provider_config.get("name", "Unknown Provider"),
                enabled=provider_config.get("enabled", False),
                issuer_url=provider_config.get("issuer_url"),
                authorization_endpoint=provider_config.get("authorization_endpoint"),
                discovery_url=provider_config.get("discovery_url"),
            ))
    
    return providers


def _validate_provider_id(provider_id: str) -> bool:
    """Validate that a provider ID exists and is enabled."""
    providers = _get_oidc_providers()
    for provider in providers:
        if provider.id == provider_id and provider.enabled:
            return True
    return False


def _get_provider_config(provider_id: str) -> Optional[Dict[str, Any]]:
    """Get full provider configuration including client credentials and endpoints."""
    if provider_id == "default":
        return {
            "client_id": OIDC_CLIENT_ID,
            "client_secret": OIDC_CLIENT_SECRET,
            "token_endpoint": OIDC_TOKEN_ENDPOINT,
            "userinfo_endpoint": OIDC_USERINFO_ENDPOINT,
        }
    for provider in OIDC_PROVIDERS:
        if provider.get("id") == provider_id:
            return provider
    return None


def _generate_state(provider_id: str, redirect_url: Optional[str] = None) -> str:
    """Generate a secure state parameter for OIDC flow."""
    state = secrets.token_urlsafe(32)
    _oidc_state_store[state] = {
        "provider_id": provider_id,
        "redirect_url": redirect_url,
        "created_at": datetime.now(),
    }
    
    # Clean up old states (older than 10 minutes)
    cutoff = datetime.now() - timedelta(minutes=10)
    old_states = [
        state_key for state_key, data in _oidc_state_store.items()
        if data["created_at"] < cutoff
    ]
    for old_state in old_states:
        del _oidc_state_store[old_state]
    
    return state


def _validate_state(state: str) -> Optional[Dict[str, Any]]:
    """Validate and retrieve state data."""
    if state not in _oidc_state_store:
        return None
    
    data = _oidc_state_store[state]
    
    # Check if state is expired (10 minutes)
    if datetime.now() - data["created_at"] > timedelta(minutes=10):
        del _oidc_state_store[state]
        return None
    
    # Clean up used state
    del _oidc_state_store[state]
    
    return data


def _sync_or_create_user_from_oidc(
    provider_id: str,
    userinfo: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Sync or create a local user from OIDC user info.
    
    Args:
        provider_id: OIDC provider identifier
        userinfo: User information from OIDC provider
    
    Returns:
        Dictionary with user information or None on failure
    """
    
    try:
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            
            # Extract user information from OIDC claims
            sub = userinfo.get("sub")  # Subject identifier
            email = userinfo.get("email")
            preferred_username = userinfo.get("preferred_username")
            name = userinfo.get("name")  # Full name, not stored in DB
            
            # Determine username (priority: preferred_username, email, sub)
            username = None
            if preferred_username:
                username = preferred_username
            elif email:
                username = email.split("@")[0]
            elif name:
                username = name.replace(" ", "_").lower()
            else:
                username = f"oidc_user_{sub[:8]}" if sub else f"oidc_user_{secrets.token_hex(4)}"
            
            # Check for existing OIDC user (using the correct get_by_oidc_id method)
            # Note: get_by_oidc_id expects (oidc_id, provider) - we need to create a composite ID
            oidc_composite_id = f"{provider_id}:{sub}"
            user = None
            
            # Search for user by OIDC email
            if email:
                existing_user = user_repo.get_by_email(email)
                if existing_user:
                    user = existing_user
            
            # If no user found by email, search by username
            if not user:
                user = user_repo.get_by_username(username)
            
            if user:
                # Update existing user with OIDC information
                update_fields = {}
                if email and email != user.email:
                    update_fields["email"] = email
                if oidc_composite_id != user.oidc_id:
                    update_fields["oidc_id"] = oidc_composite_id
                if provider_id != user.oidc_provider:
                    update_fields["oidc_provider"] = provider_id
                if email and email != user.oidc_email:
                    update_fields["oidc_email"] = email
                if not user.is_verified:
                    update_fields["is_verified"] = True
                
                if update_fields:
                    user = user_repo.update_user(user.id, **update_fields)
                    logger.info(f"Updated OIDC user: {username} (provider: {provider_id})")
                else:
                    logger.info(f"OIDC user logged in: {username}")
            else:
                # Create new user
                # First user becomes admin, others are regular users
                user_count = user_repo.count_users(active_only=False)
                role = "admin" if user_count == 0 else "user"
                
                user = user_repo.create_user(
                    username=username,
                    role=role,
                    email=email,
                    password_hash=None,
                    password_salt=None,
                    oidc_id=oidc_composite_id,
                    oidc_provider=provider_id,
                    oidc_email=email,
                )
                logger.info(f"Created new OIDC user: {username} (role: {role})")
            
            # Update last login
            if user:
                user_repo.update_last_login(user.id)
            
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            } if user else None
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error syncing OIDC user: {e}", exc_info=True)
        return None


def _build_authorization_url(
    provider: OIDCProviderInfo,
    state: str,
    redirect_uri: str,
) -> Optional[str]:
    """Build OIDC authorization URL.
    
    Args:
        provider: OIDC provider information
        state: State parameter for CSRF protection
        redirect_uri: Callback redirect URI
    
    Returns:
        Authorization URL or None if configuration is invalid
    """
    if provider.authorization_endpoint:
        # Use explicit endpoints
        params = {
            "response_type": "code",
            "client_id": OIDC_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": OIDC_SCOPES or "openid email profile",
            "state": state,
        }
        return f"{provider.authorization_endpoint}?{urlencode(params)}"
    
    elif provider.discovery_url:
        # TODO: Implement OIDC discovery
        logger.warning(f"OIDC discovery not implemented for provider: {provider.id}")
        return None
    
    return None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=OIDCProvidersResponse)
async def get_oidc_providers():
    """Get list of available OIDC providers."""
    providers = _get_oidc_providers()
    return OIDCProvidersResponse(providers=providers)


@router.post("/login")
async def oidc_login(req: OIDCLoginRequest):
    """Initiate OIDC login flow.
    
    This endpoint redirects the user to the OIDC provider's authorization page.
    """
    # Validate provider
    if not _validate_provider_id(req.provider_id):
        raise HTTPException(status_code=400, detail="Invalid or disabled OIDC provider")
    
    # Get provider info
    providers = _get_oidc_providers()
    provider = next((p for p in providers if p.id == req.provider_id), None)
    if not provider:
        raise HTTPException(status_code=400, detail="OIDC provider not found")
    
    # Generate state for CSRF protection
    state = _generate_state(provider_id=req.provider_id, redirect_url=req.redirect_url)
    
    # Build redirect URI
    redirect_uri = OIDC_REDIRECT_URI or f"{OIDC_CALLBACK_PATH}"
    if not redirect_uri.startswith("http"):
        # Assume relative path, will be constructed by client
        redirect_uri = OIDC_CALLBACK_PATH
    
    # Build authorization URL
    auth_url = _build_authorization_url(provider, state, redirect_uri)
    if not auth_url:
        raise HTTPException(status_code=500, detail="Failed to build OIDC authorization URL")
    
    # Return redirect information (frontend handles actual redirect)
    return {
        "authorization_url": auth_url,
        "state": state,
    }


@router.get("/callback")
async def oidc_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """OIDC callback endpoint.
    
    This endpoint is called by the OIDC provider after user authorization.
    """
    # Handle OIDC errors
    if error:
        error_msg = f"OIDC error: {error}"
        if error_description:
            error_msg += f" - {error_description}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is required")
    
    if not state:
        raise HTTPException(status_code=400, detail="State parameter is required")
    
    # Validate state
    state_data = _validate_state(state)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
    
    provider_id = state_data.get("provider_id", "default")
    redirect_url = state_data.get("redirect_url")
    
    try:
        # Exchange authorization code for tokens
        import httpx
        
        # Resolve provider-specific config
        provider_config = _get_provider_config(provider_id)
        client_id = provider_config.get("client_id", OIDC_CLIENT_ID) if provider_config else OIDC_CLIENT_ID
        client_secret = provider_config.get("client_secret", OIDC_CLIENT_SECRET) if provider_config else OIDC_CLIENT_SECRET
        token_url = provider_config.get("token_endpoint", OIDC_TOKEN_ENDPOINT) if provider_config else OIDC_TOKEN_ENDPOINT
        userinfo_url = provider_config.get("userinfo_endpoint", OIDC_USERINFO_ENDPOINT) if provider_config else OIDC_USERINFO_ENDPOINT
        
        redirect_uri = OIDC_REDIRECT_URI or str(request.url_for("oidc_callback"))
        
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
        
        logger.info(f"Exchanging authorization code for tokens with provider: {provider_id}")
        
        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_resp = await client.post(token_url, data=token_data)
            token_resp.raise_for_status()
            token_json = token_resp.json()
            
            access_token = token_json.get("access_token")
            if not access_token:
                raise HTTPException(status_code=500, detail="No access token in OIDC response")
            
            # Fetch user info from OIDC provider
            userinfo_url = OIDC_USERINFO_ENDPOINT
            userinfo_resp = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()
        
        logger.info(f"OIDC user info retrieved for provider: {provider_id}, sub: {userinfo.get('sub')}")
        
        # Sync or create user
        user_info = _sync_or_create_user_from_oidc(provider_id, userinfo)
        if not user_info:
            raise HTTPException(status_code=500, detail="Failed to create or sync user")
        
        # Create JWT token for CoCo
        token = create_token(
            username=user_info["username"],
            user_id=user_info["id"],
            role=user_info["role"],
        )
        
        # Redirect to frontend with token
        # The redirect_url from frontend is like: http://host/auth/oidc/callback?redirect=/chat
        # We extract the redirect path and redirect to: http://host/login/callback?token=xxx&redirect=/chat
        if redirect_url:
            parsed_url = urlparse(redirect_url)
            query_params = parse_qs(parsed_url.query)
            # Get the frontend redirect path (e.g., /chat)
            frontend_redirect = query_params.get("redirect", ["/chat"])[0]
            
            # Build redirect to frontend login callback page
            scheme = parsed_url.scheme or "http"
            netloc = parsed_url.netloc
            callback_params = urlencode({"token": token, "redirect": frontend_redirect})
            frontend_callback_url = f"{scheme}://{netloc}/login/callback?{callback_params}"
            
            return RedirectResponse(url=frontend_callback_url)
        
        # Return token in JSON response
        return OIDCCallbackResponse(
            token=token,
            username=user_info["username"],
            user_id=user_info.get("id"),
            role=user_info["role"],
            provider=provider_id,
        )
        
    except Exception as e:
        logger.error(f"OIDC callback error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OIDC authentication failed: {str(e)}")


@router.get("/status")
async def oidc_status():
    """Check OIDC configuration status."""
    providers = _get_oidc_providers()
    enabled_providers = [p for p in providers if p.enabled]
    
    return {
        "enabled": len(enabled_providers) > 0,
        "providers_configured": len(providers),
        "providers_enabled": len(enabled_providers),
    }