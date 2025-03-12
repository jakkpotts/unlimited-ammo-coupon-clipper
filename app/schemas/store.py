from pydantic import BaseModel, HttpUrl
from typing import Optional

class StoreCredentials(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str

class StoreDiscovery(BaseModel):
    url: HttpUrl
    credentials: StoreCredentials

class StoreConfig(BaseModel):
    id: Optional[int] = None
    name: str
    base_url: HttpUrl
    login_url: HttpUrl
    credentials: Optional[StoreCredentials] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Kroger",
                "base_url": "https://www.kroger.com",
                "login_url": "https://www.kroger.com/signin",
                "credentials": {
                    "email": "user@example.com",
                    "password": "password123"
                }
            }
        }

class ClipCouponsRequest(BaseModel):
    store_id: int
    credentials: StoreCredentials
    
    class Config:
        json_schema_extra = {
            "example": {
                "store_id": 1,
                "credentials": {
                    "email": "user@example.com",
                    "password": "password123"
                }
            }
        }

class StoreCreate(BaseModel):
    name: str
    base_url: HttpUrl
    login_url: HttpUrl
    credentials: StoreCredentials
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Kroger",
                "base_url": "https://www.kroger.com",
                "login_url": "https://www.kroger.com/signin",
                "credentials": {
                    "email": "user@example.com",
                    "password": "password123"
                }
            }
        }

class StoreResponse(BaseModel):
    id: int
    name: str
    base_url: HttpUrl
    login_url: HttpUrl
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Kroger",
                "base_url": "https://www.kroger.com",
                "login_url": "https://www.kroger.com/signin"
            }
        } 