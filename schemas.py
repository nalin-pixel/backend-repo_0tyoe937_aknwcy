"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import date

# Example schemas (you can keep or ignore these in your app):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Habit Breaker app schemas

class AuthUser(BaseModel):
    """
    Auth users for the application.
    Collection name: "authuser"
    """
    email: EmailStr
    password_hash: str
    display_name: Optional[str] = None

class CheckIn(BaseModel):
    """
    Daily check-ins by a user.
    Collection name: "checkin"
    """
    user_id: Optional[str] = Field(None, description="User identifier (optional for anonymous)")
    day: date = Field(default_factory=date.today, description="Calendar date of the check-in")

class TriggerJournal(BaseModel):
    """
    Journal entries capturing urges, triggers, and coping actions.
    Collection name: "triggerjournal"
    """
    user_id: Optional[str] = Field(None, description="User identifier (optional for anonymous)")
    note: str = Field(..., min_length=1, max_length=2000, description="What happened and how you coped")
    intensity: Optional[int] = Field(None, ge=1, le=10, description="Urge intensity from 1-10")
    feeling: Optional[str] = Field(None, max_length=100, description="Primary feeling (e.g., bored, stressed)")

class Goal(BaseModel):
    """
    Personal goals for streaks or habits.
    Collection name: "goal"
    """
    user_id: Optional[str] = Field(None)
    title: str = Field(..., min_length=3, max_length=100)
    target_days: int = Field(..., ge=1, le=3650)
    start_date: date = Field(default_factory=date.today)

# Add additional schemas here if needed.
