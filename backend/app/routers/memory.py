from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.memory import BusinessMemory
from app.schemas.memory import (
    BusinessMemoryCreate,
    BusinessMemoryUpdate,
    BusinessMemoryResponse,
)

router = APIRouter(prefix="/api")


@router.get("/memory", response_model=List[BusinessMemoryResponse])
def list_memories(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(BusinessMemory).order_by(
        BusinessMemory.category, BusinessMemory.updated_at.desc()
    )
    if category:
        query = query.filter(BusinessMemory.category == category)
    return query.all()


@router.get("/memory/categories", response_model=List[str])
def list_categories(db: Session = Depends(get_db)):
    rows = (
        db.query(BusinessMemory.category)
        .distinct()
        .order_by(BusinessMemory.category)
        .all()
    )
    return [r[0] for r in rows]


@router.post("/memory", response_model=BusinessMemoryResponse)
def create_memory(body: BusinessMemoryCreate, db: Session = Depends(get_db)):
    memory = BusinessMemory(
        category=body.category,
        key=body.key,
        value=body.value,
        source="manual",
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


@router.patch("/memory/{memory_id}", response_model=BusinessMemoryResponse)
def update_memory(
    memory_id: int, body: BusinessMemoryUpdate, db: Session = Depends(get_db)
):
    memory = db.query(BusinessMemory).filter(BusinessMemory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    if body.category is not None:
        memory.category = body.category
    if body.key is not None:
        memory.key = body.key
    if body.value is not None:
        memory.value = body.value
    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/memory/{memory_id}")
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    memory = db.query(BusinessMemory).filter(BusinessMemory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(memory)
    db.commit()
    return {"ok": True}


@router.delete("/memory")
def reset_all_memories(db: Session = Depends(get_db)):
    count = db.query(BusinessMemory).delete()
    db.commit()
    return {"ok": True, "deleted": count}
