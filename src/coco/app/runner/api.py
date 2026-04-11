# -*- coding: utf-8 -*-
"""Chat management API."""
from __future__ import annotations
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from agentscope.memory import InMemoryMemory

from .session import SafeJSONSession
from .manager import ChatManager
from .models import (
    ChatSpec,
    ChatUpdate,
    ChatHistory,
)
from .utils import agentscope_msg_to_message
from ..ownership import get_caller_identity, require_user_access, filter_by_user


router = APIRouter(prefix="/chats", tags=["chats"])


async def get_workspace(request: Request):
    """Get the workspace for the active agent."""
    from ..agent_context import get_agent_for_request

    return await get_agent_for_request(request)


async def get_chat_manager(
    request: Request,
) -> ChatManager:
    """Get the chat manager for the active agent.

    Args:
        request: FastAPI request object

    Returns:
        ChatManager instance for the specified agent

    Raises:
        HTTPException: If manager is not initialized
    """
    workspace = await get_workspace(request)
    return workspace.chat_manager


async def get_session(
    request: Request,
) -> SafeJSONSession:
    """Get the session for the active agent.

    Args:
        request: FastAPI request object

    Returns:
        SafeJSONSession instance for the specified agent

    Raises:
        HTTPException: If session is not initialized
    """
    workspace = await get_workspace(request)
    return workspace.runner.session


@router.get("", response_model=list[ChatSpec])
async def list_chats(
    request: Request,
    channel: Optional[str] = Query(None, description="Filter by channel"),
    mgr: ChatManager = Depends(get_chat_manager),
    workspace=Depends(get_workspace),
):
    """List all chats with optional filters.

    Non-admin users only see chats they own (user_id match).
    Admin users see all chats.

    Args:
        channel: Optional channel name to filter chats
        mgr: Chat manager dependency

    Returns:
        List of ChatSpec with runtime status
    """
    caller_id, role = get_caller_identity(request)

    # For non-admin, force user filtering
    user_filter = None if role == "admin" else caller_id

    chats = await mgr.list_chats(user_id=user_filter, channel=channel)
    tracker = workspace.task_tracker
    result = []
    for spec in chats:
        status = await tracker.get_status(spec.id)
        result.append(spec.model_copy(update={"status": status}))
    return result


@router.post("", response_model=ChatSpec)
async def create_chat(
    request: Request,
    chat_request: ChatSpec,
    mgr: ChatManager = Depends(get_chat_manager),
):
    """Create a new chat.

    Server generates chat_id (UUID) automatically.
    user_id is automatically set from the authenticated user.

    Args:
        chat_request: Chat creation request
        mgr: Chat manager dependency

    Returns:
        Created chat spec with UUID
    """
    caller_id, role = get_caller_identity(request)

    chat_id = str(uuid4())
    spec = ChatSpec(
        id=chat_id,
        name=chat_request.name,
        session_id=chat_request.session_id,
        user_id=caller_id,  # Always from auth
        channel=chat_request.channel,
        meta=chat_request.meta,
    )
    return await mgr.create_chat(spec)


@router.post("/batch-delete", response_model=dict)
async def batch_delete_chats(
    request: Request,
    chat_ids: list[str],
    mgr: ChatManager = Depends(get_chat_manager),
):
    """Delete chats by chat IDs.

    Non-admin users can only delete chats they own.

    Args:
        chat_ids: List of chat IDs
        mgr: Chat manager dependency

    Returns:
        Dict with deleted count
    """
    caller_id, role = get_caller_identity(request)

    # For non-admin, filter out chats they don't own
    if role != "admin":
        allowed_ids = []
        for cid in chat_ids:
            chat = await mgr.get_chat(cid)
            if chat and chat.user_id == caller_id:
                allowed_ids.append(cid)
        chat_ids = allowed_ids

    deleted = await mgr.delete_chats(chat_ids=chat_ids)
    return {"deleted": deleted}


@router.get("/{chat_id}", response_model=ChatHistory)
async def get_chat(
    request: Request,
    chat_id: str,
    mgr: ChatManager = Depends(get_chat_manager),
    session: SafeJSONSession = Depends(get_session),
    workspace=Depends(get_workspace),
):
    """Get detailed information about a specific chat by UUID.

    Non-admin users can only access chats they own.

    Args:
        chat_id: Chat UUID
        mgr: Chat manager dependency
        session: SafeJSONSession dependency

    Returns:
        ChatHistory with messages and status (idle/running)

    Raises:
        HTTPException: If chat not found (404)
    """
    caller_id, role = get_caller_identity(request)

    chat_spec = await mgr.get_chat(chat_id)
    if not chat_spec:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found: {chat_id}",
        )

    # Ownership check
    require_user_access(caller_id, role, chat_spec.user_id)

    state = await session.get_session_state_dict(
        chat_spec.session_id,
        chat_spec.user_id,
    )
    status = await workspace.task_tracker.get_status(chat_id)
    if not state:
        return ChatHistory(messages=[], status=status)
    memory_state = state.get("agent", {}).get("memory", {})
    memory = InMemoryMemory()
    memory.load_state_dict(memory_state, strict=False)

    memories = await memory.get_memory(prepend_summary=False)
    messages = agentscope_msg_to_message(memories)
    return ChatHistory(messages=messages, status=status)


@router.put("/{chat_id}", response_model=ChatSpec)
async def update_chat(
    request: Request,
    chat_id: str,
    spec: ChatUpdate,
    mgr: ChatManager = Depends(get_chat_manager),
):
    """Update an existing chat.

    Non-admin users can only update chats they own.

    Args:
        chat_id: Chat UUID
        spec: Partial chat update payload
        mgr: Chat manager dependency

    Returns:
        Updated chat spec

    Raises:
        HTTPException: If chat not found (404)
    """
    caller_id, role = get_caller_identity(request)

    existing = await mgr.get_chat(chat_id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found: {chat_id}",
        )

    # Ownership check
    require_user_access(caller_id, role, existing.user_id)

    updated = await mgr.patch_chat(chat_id, spec)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found: {chat_id}",
        )
    return updated


@router.delete("/{chat_id}", response_model=dict)
async def delete_chat(
    request: Request,
    chat_id: str,
    mgr: ChatManager = Depends(get_chat_manager),
):
    """Delete a chat by UUID.

    Note: This only deletes the chat spec (UUID mapping).
    JSONSession state is NOT deleted.
    Non-admin users can only delete chats they own.

    Args:
        chat_id: Chat UUID
        mgr: Chat manager dependency

    Returns:
        Dict with deleted confirmation

    Raises:
        HTTPException: If chat not found (404)
    """
    caller_id, role = get_caller_identity(request)

    chat = await mgr.get_chat(chat_id)
    if not chat:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found: {chat_id}",
        )

    # Ownership check
    require_user_access(caller_id, role, chat.user_id)

    deleted = await mgr.delete_chats(chat_ids=[chat_id])
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found: {chat_id}",
        )
    return {"deleted": True}
