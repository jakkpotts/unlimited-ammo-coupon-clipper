from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.store import StoreConfig, StoreDiscovery, ClipCouponsRequest
from app.services.coupon_service import DynamicCouponService
from app.services.store_discovery import StoreDiscoveryService
from app.db.base import get_db
from app.db.models.store import Store
from app.db.models.user import User, user_stores
from sqlalchemy import select, and_
from typing import Dict, Any, List
from app.api.deps import get_current_active_user

router = APIRouter(
    prefix="/coupons",
    tags=["coupons"],
    responses={404: {"description": "Not found"}},
)

@router.post("/discover-store")
async def discover_store(
    discovery: StoreDiscovery,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Discover and analyze a store website using just the URL.
    If login verification is successful, store information is saved and associated with the user.
    
    Example request body:
    ```json
    {
        "url": "https://www.kroger.com",
        "credentials": {
            "email": "user@example.com",
            "password": "your_password_here"
        }
    }
    ```
    """
    discovery_service = StoreDiscoveryService()
    
    # Analyze store website
    store_config = await discovery_service.analyze_store(discovery)
    if not store_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to analyze store website. Please check the URL."
        )
    
    # Check if store already exists
    query = select(Store).where(Store.base_url == str(store_config.base_url))
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
            name=store_config.name,
            base_url=str(store_config.base_url),
            login_url=str(store_config.login_url)
        )
        db.add(store)
    
    # Verify credentials work
    if not await discovery_service.verify_login(store_config, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to verify store credentials"
        )
    
    # Associate store with user
    store.users.append(current_user)
    await db.commit()
    await db.refresh(store)
    
    store_config.id = store.id
    return {
        "status": "success",
        "message": "Store discovered and added to your account",
        "store": store_config
    }

@router.get("/stores", response_model=List[StoreConfig])
async def list_stores(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> List[StoreConfig]:
    """List all stores for the current user"""
    return [
        StoreConfig(
            id=store.id,
            name=store.name,
            base_url=store.base_url,
            login_url=store.login_url
        ) for store in current_user.stores
    ]

@router.post("/{store_id}/clip", response_model=Dict[str, Any])
async def clip_store_coupons(
    store_id: int,
    clip_request: ClipCouponsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Clip all available coupons for a store"""
    # Verify user has access to store using async query
    query = select(Store).join(user_stores).where(
        and_(
            user_stores.c.user_id == current_user.id,
            user_stores.c.store_id == store_id
        )
    )
    result = await db.execute(query)
    store = result.scalar_one_or_none()
    
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )
    
    # Create store config from store and provided credentials
    store_config = StoreConfig(
        id=store.id,
        name=store.name,
        base_url=store.base_url,
        login_url=store.login_url,
        credentials=clip_request.credentials
    )
    
    # Initialize coupon service and clip coupons
    coupon_service = DynamicCouponService()
    result = await coupon_service.clip_coupons(store_config, current_user.id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to clip coupons")
        )
    
    return result

@router.post("/clip-all", response_model=Dict[str, Any])
async def clip_all_stores_coupons(
    clip_request: ClipCouponsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Clip coupons for all user's stores"""
    # Get all stores for the user
    query = select(Store).join(user_stores).where(user_stores.c.user_id == current_user.id)
    result = await db.execute(query)
    stores = result.scalars().all()
    
    results = []
    coupon_service = DynamicCouponService()
    
    for store in stores:
        store_config = StoreConfig(
            id=store.id,
            name=store.name,
            base_url=store.base_url,
            login_url=store.login_url,
            credentials=clip_request.credentials
        )
        
        result = await coupon_service.clip_coupons(store_config, current_user.id)
        results.append({
            "store": store.name,
            "success": result["success"],
            "clipped_coupons": result["clipped_coupons"],
            "error": result.get("error")
        })
    
    return {
        "results": results,
        "total_stores": len(results),
        "successful_stores": sum(1 for r in results if r["success"]),
        "total_coupons_clipped": sum(len(r["clipped_coupons"]) for r in results)
    } 