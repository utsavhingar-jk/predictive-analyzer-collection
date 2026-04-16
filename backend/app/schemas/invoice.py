"""Pydantic schemas for invoice and customer payloads."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CustomerBase(BaseModel):
    name: str
    industry: Optional[str] = None
    credit_score: Optional[int] = None
    payment_terms: int = 30
    avg_days_to_pay: float = 0.0
    total_invoiced: Decimal = Decimal("0")
    total_overdue: Decimal = Decimal("0")


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class InvoiceBase(BaseModel):
    invoice_number: str
    customer_id: int
    amount: Decimal
    currency: str = "INR"
    issue_date: date
    due_date: date
    paid_date: Optional[date] = None
    status: str = "open"
    days_overdue: int = 0
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceRead(InvoiceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    customer: Optional[CustomerRead] = None
