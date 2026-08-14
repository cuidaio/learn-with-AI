"""
M3: 文件夹 CRUD API。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Folder
from app.schemas import (
    FolderCreate,
    FolderListResponse,
    FolderResponse,
    FolderUpdate,
)

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("", response_model=FolderListResponse)
def list_folders(db: Session = Depends(get_db)):
    folders = db.query(Folder).order_by(Folder.position, Folder.name).all()
    return FolderListResponse(folders=[
        FolderResponse(id=f.id, name=f.name, parent_id=f.parent_id, position=f.position, created_at=f.created_at)
        for f in folders
    ])


@router.post("", response_model=FolderResponse, status_code=201)
def create_folder(payload: FolderCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name cannot be empty")

    folder = Folder(
        id=uuid.uuid4(),
        name=name,
        parent_id=payload.parent_id,
        position=0,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return FolderResponse(id=folder.id, name=folder.name, parent_id=folder.parent_id, position=folder.position, created_at=folder.created_at)


@router.put("/{folder_id}", response_model=FolderResponse)
def update_folder(folder_id: uuid.UUID, payload: FolderUpdate, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if payload.name is not None:
        folder.name = payload.name.strip()
    if payload.parent_id is not None:
        folder.parent_id = payload.parent_id
    if payload.position is not None:
        folder.position = payload.position

    db.commit()
    db.refresh(folder)
    return FolderResponse(id=folder.id, name=folder.name, parent_id=folder.parent_id, position=folder.position, created_at=folder.created_at)


@router.delete("/{folder_id}", status_code=204)
def delete_folder(folder_id: uuid.UUID, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # 将子文件夹设为根级
    db.query(Folder).filter(Folder.parent_id == folder_id).update({"parent_id": None})

    # 取消文档的文件夹关联
    from app.models import Document as DocModel
    db.query(DocModel).filter(DocModel.folder_id == folder_id).update({"folder_id": None})

    db.delete(folder)
    db.commit()
