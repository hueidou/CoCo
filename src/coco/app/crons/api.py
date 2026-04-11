# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request

from .manager import CronManager
from .models import CronJobSpec, CronJobView
from ..ownership import get_caller_identity, require_user_access

router = APIRouter(prefix="/cron", tags=["cron"])


async def get_cron_manager(
    request: Request,
) -> CronManager:
    """Get cron manager for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.cron_manager is None:
        raise HTTPException(
            status_code=500,
            detail="CronManager not initialized",
        )
    return workspace.cron_manager


@router.get("/jobs", response_model=list[CronJobSpec])
async def list_jobs(request: Request, mgr: CronManager = Depends(get_cron_manager)):
    """List all cron jobs. Non-admin only sees their own + unowned jobs."""
    caller_id, role = get_caller_identity(request)
    user_filter = None if role == "admin" else caller_id
    return await mgr.list_jobs(user_id=user_filter)


@router.get("/jobs/{job_id}", response_model=CronJobView)
async def get_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Get a cron job by ID. Non-admin can only access their own + unowned."""
    caller_id, role = get_caller_identity(request)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    require_user_access(caller_id, role, job.user_id)
    return CronJobView(spec=job, state=mgr.get_state(job_id))


@router.post("/jobs", response_model=CronJobSpec)
async def create_job(
    request: Request,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Create a new cron job. user_id is automatically set."""
    caller_id, role = get_caller_identity(request)
    job_id = str(uuid.uuid4())
    created = spec.model_copy(update={"id": job_id, "user_id": caller_id})
    await mgr.create_or_replace_job(created)
    return created


@router.put("/jobs/{job_id}", response_model=CronJobSpec)
async def replace_job(
    request: Request,
    job_id: str,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Replace a cron job. Non-admin can only replace their own."""
    caller_id, role = get_caller_identity(request)
    if spec.id != job_id:
        raise HTTPException(status_code=400, detail="job_id mismatch")
    # Check ownership of existing job
    existing = await mgr.get_job(job_id)
    if existing:
        require_user_access(caller_id, role, existing.user_id)
    # Set user_id on the replacement
    updated = spec.model_copy(update={"user_id": caller_id if existing is None else existing.user_id})
    await mgr.create_or_replace_job(updated)
    return updated


@router.delete("/jobs/{job_id}")
async def delete_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Delete a cron job. Non-admin can only delete their own."""
    caller_id, role = get_caller_identity(request)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    require_user_access(caller_id, role, job.user_id)
    ok = await mgr.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"deleted": True}


@router.post("/jobs/{job_id}/pause")
async def pause_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Pause a cron job. Non-admin can only pause their own."""
    caller_id, role = get_caller_identity(request)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    require_user_access(caller_id, role, job.user_id)
    try:
        await mgr.pause_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"paused": True}


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Resume a cron job. Non-admin can only resume their own."""
    caller_id, role = get_caller_identity(request)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    require_user_access(caller_id, role, job.user_id)
    try:
        await mgr.resume_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"resumed": True}


@router.post("/jobs/{job_id}/run")
async def run_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Run a cron job. Non-admin can only run their own."""
    caller_id, role = get_caller_identity(request)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    require_user_access(caller_id, role, job.user_id)
    try:
        await mgr.run_job(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"started": True}


@router.get("/jobs/{job_id}/state")
async def get_job_state(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    """Get a cron job's state. Non-admin can only view their own."""
    caller_id, role = get_caller_identity(request)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    require_user_access(caller_id, role, job.user_id)
    return mgr.get_state(job_id).model_dump(mode="json")
