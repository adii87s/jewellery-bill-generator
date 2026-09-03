from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as OrmSession, joinedload

from .. import models, schemas
from ..database import get_db


# Login/authentication removed.
# Bills can now be created, viewed, updated, and deleted without a session.
router = APIRouter(
    prefix="/api/bills",
    tags=["bills"],
)

TWO_PLACES = Decimal("0.01")


def _q(value) -> Decimal:
    return Decimal(value).quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _compute_totals(payload: schemas.BillIn):
    """
    Server-side recomputation of every derived financial value.

    The frontend may show a live preview, but this function is
    the single source of truth for values that are persisted.
    """

    item_rows = []
    subtotal = Decimal("0")

    for item in payload.items:
        net_weight = item.gross_weight - item.less_weight

        if net_weight < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Item '{item.item_name}': "
                    "less_weight cannot exceed gross_weight"
                ),
            )

        item_total = _q(
            net_weight * item.rate + item.labour
        )

        subtotal += item_total

        item_rows.append(
            {
                "item_name": item.item_name,
                "gross_weight": item.gross_weight,
                "less_weight": item.less_weight,
                "net_weight": net_weight,
                "rate": item.rate,
                "labour": item.labour,
                "item_total": item_total,
            }
        )

    subtotal = _q(subtotal)

    cgst_amount = _q(
        subtotal * payload.cgst_percent / Decimal("100")
    )

    sgst_amount = _q(
        subtotal * payload.sgst_percent / Decimal("100")
    )

    grand_total = _q(
        subtotal + cgst_amount + sgst_amount
    )

    due_amount = _q(
        grand_total
        - (
            payload.received_online
            + payload.received_cash
        )
    )

    return (
        item_rows,
        subtotal,
        cgst_amount,
        sgst_amount,
        grand_total,
        due_amount,
    )


# ============================================================
# CREATE BILL
# ============================================================

@router.post(
    "",
    response_model=schemas.BillOut,
    status_code=status.HTTP_201_CREATED,
)
def create_bill(
    payload: schemas.BillIn,
    db: OrmSession = Depends(get_db),
):
    (
        item_rows,
        subtotal,
        cgst_amount,
        sgst_amount,
        grand_total,
        due_amount,
    ) = _compute_totals(payload)

    try:
        bill = models.Bill(
            bill_date=payload.bill_date,
            customer_name=payload.customer_name,
            customer_mobile=payload.customer_mobile,
            customer_address=payload.customer_address,

            shop_name=payload.shop_name,
            shop_name_local=payload.shop_name_local,
            shop_address=payload.shop_address,
            shop_gstin=payload.shop_gstin,
            shop_phone1=payload.shop_phone1,
            shop_phone2=payload.shop_phone2,
            shop_insta=payload.shop_insta,

            subtotal=subtotal,

            cgst_percent=payload.cgst_percent,
            sgst_percent=payload.sgst_percent,

            cgst_amount=cgst_amount,
            sgst_amount=sgst_amount,

            grand_total=grand_total,

            received_online=payload.received_online,
            received_cash=payload.received_cash,

            due_amount=due_amount,

            payment_mode=payload.payment_mode,

            note=payload.note,
            terms=payload.terms,

            stamp_image=payload.stamp_image,
        )

        bill.items = [
            models.BillItem(**row)
            for row in item_rows
        ]

        db.add(bill)
        db.commit()
        db.refresh(bill)

    except HTTPException:
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save bill",
        )

    return bill


# ============================================================
# LIST BILLS
# ============================================================

@router.get(
    "",
    response_model=List[schemas.BillListOut],
)
def list_bills(
    db: OrmSession = Depends(get_db),
    bill_number: Optional[int] = Query(default=None),
    customer_name: Optional[str] = Query(default=None),
    customer_mobile: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    q = (
        db.query(models.Bill)
        .options(joinedload(models.Bill.items))
    )

    if bill_number is not None:
        q = q.filter(
            models.Bill.id == bill_number
        )

    if customer_name:
        q = q.filter(
            models.Bill.customer_name.ilike(
                f"%{customer_name}%"
            )
        )

    if customer_mobile:
        q = q.filter(
            models.Bill.customer_mobile.ilike(
                f"%{customer_mobile}%"
            )
        )

    if date_from:
        q = q.filter(
            models.Bill.bill_date >= date_from
        )

    if date_to:
        q = q.filter(
            models.Bill.bill_date <= date_to
        )

    bills = (
        q.order_by(
            models.Bill.bill_date.desc(),
            models.Bill.id.desc(),
        )
        .all()
    )

    return bills


# ============================================================
# GET SINGLE BILL
# ============================================================

@router.get(
    "/{bill_id}",
    response_model=schemas.BillOut,
)
def get_bill(
    bill_id: int,
    db: OrmSession = Depends(get_db),
):
    bill = (
        db.query(models.Bill)
        .options(joinedload(models.Bill.items))
        .filter(models.Bill.id == bill_id)
        .first()
    )

    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found",
        )

    return bill


# ============================================================
# UPDATE BILL
# ============================================================

@router.put(
    "/{bill_id}",
    response_model=schemas.BillOut,
)
def update_bill(
    bill_id: int,
    payload: schemas.BillIn,
    db: OrmSession = Depends(get_db),
):
    bill = (
        db.query(models.Bill)
        .filter(models.Bill.id == bill_id)
        .first()
    )

    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found",
        )

    (
        item_rows,
        subtotal,
        cgst_amount,
        sgst_amount,
        grand_total,
        due_amount,
    ) = _compute_totals(payload)

    try:
        bill.bill_date = payload.bill_date

        bill.customer_name = payload.customer_name
        bill.customer_mobile = payload.customer_mobile
        bill.customer_address = payload.customer_address

        bill.shop_name = payload.shop_name
        bill.shop_name_local = payload.shop_name_local
        bill.shop_address = payload.shop_address
        bill.shop_gstin = payload.shop_gstin
        bill.shop_phone1 = payload.shop_phone1
        bill.shop_phone2 = payload.shop_phone2
        bill.shop_insta = payload.shop_insta

        bill.subtotal = subtotal

        bill.cgst_percent = payload.cgst_percent
        bill.sgst_percent = payload.sgst_percent

        bill.cgst_amount = cgst_amount
        bill.sgst_amount = sgst_amount

        bill.grand_total = grand_total

        bill.received_online = payload.received_online
        bill.received_cash = payload.received_cash

        bill.due_amount = due_amount

        bill.payment_mode = payload.payment_mode

        bill.note = payload.note
        bill.terms = payload.terms

        bill.stamp_image = payload.stamp_image

        # Replace existing items.
        # Bill ID / bill number is never changed.
        bill.items.clear()

        db.flush()

        bill.items = [
            models.BillItem(**row)
            for row in item_rows
        ]

        db.commit()
        db.refresh(bill)

    except HTTPException:
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update bill",
        )

    return bill


# ============================================================
# DELETE BILL
# ============================================================

@router.delete(
    "/{bill_id}",
    response_model=schemas.MessageOut,
)
def delete_bill(
    bill_id: int,
    db: OrmSession = Depends(get_db),
):
    bill = (
        db.query(models.Bill)
        .filter(models.Bill.id == bill_id)
        .first()
    )

    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found",
        )

    try:
        db.delete(bill)
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete bill",
        )

    return {
        "message": f"Bill #{bill_id} deleted"
    }