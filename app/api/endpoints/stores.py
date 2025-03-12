from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlalchemy import select

from app.db.base import get_db
from app.db.models.store import Store
from app.db.models.user import User
from app.schemas.store import StoreCreate, StoreResponse, StoreConfig
from app.services.store_discovery import StoreDiscoveryService
from app.api.deps import get_current_active_user

router = APIRouter(
    prefix="/stores",
    tags=["stores"]
)

@router.post("/", response_model=StoreResponse)
async def add_store(
    store_data: StoreCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Store:
    """Add a new store with credentials verification"""
    # Check if store already exists
    query = select(Store).where(Store.base_url == store_data.base_url)
    result = await db.execute(query)
    existing_store = result.scalar_one_or_none()
    
    if existing_store:
        # If store exists, verify user doesn't already have access
        if current_user in existing_store.users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Store already added to your account"
            )
        store = existing_store
    else:
        # Create new store
        store = Store(
            name=store_data.name,
            base_url=store_data.base_url,
            login_url=store_data.login_url
        )
        db.add(store)
    
    # Verify credentials work
    discovery_service = StoreDiscoveryService()
    store_config = StoreConfig(
        name=store_data.name,
        base_url=store_data.base_url,
        login_url=store_data.login_url,
        credentials=store_data.credentials
    )
    
    if not await discovery_service.verify_login(store_config, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid store credentials"
        )
    
    # Associate store with user
    store.users.append(current_user)
    await db.commit()
    await db.refresh(store)
    
    return store

@router.get("/", response_model=List[StoreResponse])
async def get_stores(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> List[Store]:
    """Get all stores for the current user"""
    return current_user.stores

@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Store:
    """Get a specific store if user has access"""
    store = next((s for s in current_user.stores if s.id == store_id), None)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )
    return store

@router.delete("/{store_id}")
async def remove_store(
    store_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove store from user's account"""
    store = next((s for s in current_user.stores if s.id == store_id), None)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )
    
    current_user.stores.remove(store)
    await db.commit()
    
    return {"message": "Store removed successfully"} 