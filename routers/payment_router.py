from fastapi import APIRouter
from pydantic import BaseModel
from database import db, firestore
import random

router = APIRouter(prefix="/api", tags=["Payment"])

class PaymentRequest(BaseModel):
    user_id: str
    order_id: str
    amount: float
    payment_method: str = "cod"

@router.post("/payment")
def process_payment(payment: PaymentRequest):
    print(f"Processing Payment: {payment.order_id}")
    if random.random() > 0.1:
        try:
            db.collection('orders').document(payment.order_id).update({
                'paymentStatus': 'PAID', 'status': 'PROCESSING', 'updatedAt': firestore.SERVER_TIMESTAMP
            })
            return {"status": "success", "transaction_id": f"TXN-{random.randint(10000,99999)}"}
        except Exception as e: return {"status": "failed", "message": str(e)}
    return {"status": "failed", "message": "Payment Error!"}