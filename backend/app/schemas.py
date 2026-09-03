import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class MeOut(BaseModel):
    username: str


class MessageOut(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Bill items
# ---------------------------------------------------------------------------
class BillItemIn(BaseModel):
    item_name: str = Field(min_length=1, max_length=255)
    gross_weight: Decimal = Field(ge=0)
    less_weight: Decimal = Field(ge=0)
    rate: Decimal = Field(ge=0)
    labour: Decimal = Field(ge=0)

    @field_validator("item_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("item_name cannot be blank")
        return v

    @field_validator("less_weight")
    @classmethod
    def less_not_more_than_gross(cls, v, info):
        gross = info.data.get("gross_weight")
        if gross is not None and v > gross:
            raise ValueError("less_weight cannot exceed gross_weight")
        return v


class BillItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_name: str
    gross_weight: Decimal
    less_weight: Decimal
    net_weight: Decimal
    rate: Decimal
    labour: Decimal
    item_total: Decimal


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------
class ShopDetails(BaseModel):
    shop_name: str = ""
    shop_name_local: str = ""
    shop_address: str = ""
    shop_gstin: str = ""
    shop_phone1: str = ""
    shop_phone2: str = ""
    shop_insta: str = ""


class BillIn(ShopDetails):
    bill_date: datetime.date
    customer_name: str = Field(min_length=1, max_length=255)
    customer_mobile: str = Field(default="", max_length=32)
    customer_address: str = Field(default="", max_length=2000)

    items: List[BillItemIn] = Field(min_length=1)

    cgst_percent: Decimal = Field(ge=0, le=100, default=Decimal("0"))
    sgst_percent: Decimal = Field(ge=0, le=100, default=Decimal("0"))

    received_online: Decimal = Field(ge=0, default=Decimal("0"))
    received_cash: Decimal = Field(ge=0, default=Decimal("0"))
    payment_mode: str = Field(default="Online", max_length=64)

    note: str = Field(default="", max_length=2000)
    terms: str = Field(default="", max_length=4000)
    stamp_image: Optional[str] = None

    @field_validator("customer_name")
    @classmethod
    def strip_customer_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("customer_name cannot be blank")
        return v

    @field_validator("customer_mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        v = (v or "").strip()
        if v == "":
            return v
        digits = "".join(ch for ch in v if ch.isdigit())
        if len(digits) < 7:
            raise ValueError("customer_mobile does not look like a valid phone number")
        return v


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_number: int
    bill_date: datetime.date

    customer_name: str
    customer_mobile: str
    customer_address: str

    shop_name: str
    shop_name_local: str
    shop_address: str
    shop_gstin: str
    shop_phone1: str
    shop_phone2: str
    shop_insta: str

    subtotal: Decimal
    cgst_percent: Decimal
    sgst_percent: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    grand_total: Decimal

    received_online: Decimal
    received_cash: Decimal
    due_amount: Decimal
    payment_mode: str

    note: str
    terms: str
    stamp_image: Optional[str] = None

    created_at: datetime.datetime
    updated_at: datetime.datetime

    items: List[BillItemOut]


class BillListOut(BaseModel):
    """Lighter-weight shape used for the records list / search endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_number: int
    bill_date: datetime.date
    customer_name: str
    customer_mobile: str
    grand_total: Decimal
    received_online: Decimal
    received_cash: Decimal
    due_amount: Decimal
    payment_mode: str
    items: List[BillItemOut]
