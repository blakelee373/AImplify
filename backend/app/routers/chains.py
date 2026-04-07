"""Workflow chain (journey) management endpoints."""

from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.workflow_chain import WorkflowChain, WorkflowChainLink
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution

router = APIRouter()


class ChainUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    pause_all: Optional[bool] = None
    resume_all: Optional[bool] = None


@router.get("/chains")
async def list_chains(db: Session = Depends(get_db)):
    chains = db.query(WorkflowChain).order_by(desc(WorkflowChain.created_at)).all()
    result = []
    for chain in chains:
        workflows = []
        statuses = set()
        for link in chain.links:
            wf = db.query(Workflow).filter(Workflow.id == link.workflow_id).first()
            if wf:
                workflows.append({
                    "id": wf.id,
                    "name": wf.name,
                    "position": link.position,
                    "delay_after_previous": link.delay_after_previous,
                    "status": wf.status,
                })
                statuses.add(wf.status)

        # Overall chain status
        if "active" in statuses:
            overall = "active"
        elif "testing" in statuses:
            overall = "testing"
        elif "paused" in statuses:
            overall = "paused"
        else:
            overall = "draft"

        result.append({
            "id": chain.id,
            "name": chain.name,
            "description": chain.description,
            "workflow_count": len(workflows),
            "workflows": workflows,
            "overall_status": overall,
            "created_at": chain.created_at.isoformat(),
        })
    return result


@router.get("/chains/{chain_id}")
async def get_chain(chain_id: str, db: Session = Depends(get_db)):
    chain = db.query(WorkflowChain).filter(WorkflowChain.id == chain_id).first()
    if not chain:
        raise HTTPException(404, "Chain not found")

    workflows = []
    for link in chain.links:
        wf = db.query(Workflow).filter(Workflow.id == link.workflow_id).first()
        if not wf:
            continue

        last_exec = (
            db.query(WorkflowExecution)
            .filter(WorkflowExecution.workflow_id == wf.id, WorkflowExecution.status != "dry_run")
            .order_by(desc(WorkflowExecution.started_at))
            .first()
        )

        workflows.append({
            "id": wf.id,
            "name": wf.name,
            "description": wf.description,
            "position": link.position,
            "delay_after_previous": link.delay_after_previous,
            "condition_from_previous": link.condition_from_previous,
            "status": wf.status,
            "last_run_at": last_exec.started_at.isoformat() if last_exec else None,
        })

    return {
        "id": chain.id,
        "name": chain.name,
        "description": chain.description,
        "created_at": chain.created_at.isoformat(),
        "workflows": workflows,
    }


@router.patch("/chains/{chain_id}")
async def update_chain(chain_id: str, update: ChainUpdate, db: Session = Depends(get_db)):
    chain = db.query(WorkflowChain).filter(WorkflowChain.id == chain_id).first()
    if not chain:
        raise HTTPException(404, "Chain not found")

    if update.name is not None:
        chain.name = update.name
    if update.description is not None:
        chain.description = update.description

    # Pause/resume all workflows in the chain
    if update.pause_all:
        for link in chain.links:
            wf = db.query(Workflow).filter(Workflow.id == link.workflow_id).first()
            if wf and wf.status == "active":
                wf.status = "paused"
    elif update.resume_all:
        for link in chain.links:
            wf = db.query(Workflow).filter(Workflow.id == link.workflow_id).first()
            if wf and wf.status == "paused":
                wf.status = "active"

    db.commit()
    return {"status": "updated"}


@router.delete("/chains/{chain_id}")
async def delete_chain(chain_id: str, delete_workflows: bool = False, db: Session = Depends(get_db)):
    chain = db.query(WorkflowChain).filter(WorkflowChain.id == chain_id).first()
    if not chain:
        raise HTTPException(404, "Chain not found")

    if delete_workflows:
        for link in chain.links:
            wf = db.query(Workflow).filter(Workflow.id == link.workflow_id).first()
            if wf:
                wf.deleted_at = datetime.now(timezone.utc)

    # Delete links and chain
    db.query(WorkflowChainLink).filter(WorkflowChainLink.chain_id == chain_id).delete()
    db.delete(chain)
    db.commit()
    return {"status": "deleted"}
