"""
SQLAlchemy ORM models.

Money values use Numeric (fixed-point) instead of Float to avoid binary
floating point rounding errors. Weights use Numeric(12,3) for gram-level
precision.

Bill numbering: `Bill.bill_number` is backed by the table's own identity
column (`id`). PostgreSQL identity/serial columns are generated atomically
by the database, so two simultaneous "create bill" requests can never
receive the same number, and the counter survives server restarts. This is
NOT the same as legally-mandated "gap-free" invoice numbering (a rolled-back
transaction can still consume a number) — if your jurisdiction requires
strictly gap-free sequential invoices, that is a business/accounting
requirement that needs a separate, dedicated design and should be confirmed
with an accountant, not assumed from this implementation.
"""
import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class AdminUser(Base):
    """Single shop-owner account. The app only supports one admin login
    (matching the original single-password login screen), but this is
    modelled as a table row (rather than a hardcoded constant) so the
    password hash lives in the database and can be rotated without a
    code deploy."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, unique=True, default="admin")
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Session(Base):
    """Server-side session store backing the HttpOnly session cookie."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    admin_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True)  # doubles as the bill number
    bill_date = Column(Date, nullable=False, default=datetime.date.today)

    customer_name = Column(String(255), nullable=False)
    customer_mobile = Column(String(32), nullable=False, default="")
    customer_address = Column(Text, nullable=False, default="")

    # Shop details are snapshotted onto the bill at creation time so that
    # historical bills stay accurate even if shop info is edited later.
    shop_name = Column(String(255), nullable=False, default="")
    shop_name_local = Column(String(255), nullable=False, default="")
    shop_address = Column(Text, nullable=False, default="")
    shop_gstin = Column(String(32), nullable=False, default="")
    shop_phone1 = Column(String(32), nullable=False, default="")
    shop_phone2 = Column(String(32), nullable=False, default="")
    shop_insta = Column(String(128), nullable=False, default="")

    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    cgst_percent = Column(Numeric(5, 2), nullable=False, default=0)
    sgst_percent = Column(Numeric(5, 2), nullable=False, default=0)
    cgst_amount = Column(Numeric(14, 2), nullable=False, default=0)
    sgst_amount = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)

    received_online = Column(Numeric(14, 2), nullable=False, default=0)
    received_cash = Column(Numeric(14, 2), nullable=False, default=0)
    due_amount = Column(Numeric(14, 2), nullable=False, default=0)
    payment_mode = Column(String(64), nullable=False, default="Online")

    note = Column(Text, nullable=False, default="")
    terms = Column(Text, nullable=False, default="")
    stamp_image = Column(Text, nullable=True)  # base64 data URL, optional

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    items = relationship(
        "BillItem",
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillItem.id",
    )

    @property
    def bill_number(self):
        return self.id


class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)

    item_name = Column(String(255), nullable=False, default="")
    gross_weight = Column(Numeric(12, 3), nullable=False, default=0)
    less_weight = Column(Numeric(12, 3), nullable=False, default=0)
    net_weight = Column(Numeric(12, 3), nullable=False, default=0)
    rate = Column(Numeric(14, 2), nullable=False, default=0)
    labour = Column(Numeric(14, 2), nullable=False, default=0)
    item_total = Column(Numeric(14, 2), nullable=False, default=0)

    bill = relationship("Bill", back_populates="items")
