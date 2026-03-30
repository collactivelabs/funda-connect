# 05 — Payment Integration

> **Status:** Draft  
> **Last Updated:** 2026-03-25  
> **Primary Gateway:** PayFast (payfast.io)  
> **Currency:** ZAR (South African Rand)

---

## 1. Overview

FundaConnect uses an **escrow-style payment flow**: parents pay upfront when booking a lesson. Funds are held by the platform until the lesson is confirmed as completed, at which point the platform commission is deducted and the teacher's share is queued for payout.

Current gateway scope as of March 30, 2026:

- **PayFast** is the implemented gateway in the live codebase
- **Ozow** remains in planned scope, with implementation pending after PayFast

### 1.1 Recurring Lesson Billing Decision

Recurring lessons currently use a **prepaid weekly series** model.

- Parents pick one weekly slot and a lesson count
- PayFast charges the **full series amount once** at checkout
- The root booking is paid first, then the remaining weekly child bookings are created after payment confirmation
- Refunds, disputes, rescheduling, and payouts are still tracked per lesson

True subscription rebilling for recurring lessons is intentionally deferred.

---

## 2. Payment Flow

```
┌────────┐          ┌──────────┐         ┌─────────┐         ┌─────────┐
│ Parent │          │ FundaAPI │         │ PayFast │         │ Teacher │
└───┬────┘          └────┬─────┘         └────┬────┘         └────┬────┘
    │  1. Book lesson    │                    │                    │
    │ ─────────────────► │                    │                    │
    │                    │ 2. Create booking  │                    │
    │                    │   (pending_payment)│                    │
    │                    │                    │                    │
    │                    │ 3. Generate PayFast│                    │
    │                    │    payment request │                    │
    │  4. Redirect URL   │                    │                    │
    │ ◄───────────────── │                    │                    │
    │                    │                    │                    │
    │  5. Pay on PayFast ──────────────────►  │                    │
    │                    │                    │                    │
    │                    │ 6. ITN webhook     │                    │
    │                    │ ◄──────────────────│                    │
    │                    │ 7. Validate ITN    │                    │
    │                    │    signature       │                    │
    │                    │ 8. Update booking  │                    │
    │                    │    → confirmed     │                    │
    │  9. Confirmation   │                    │                    │
    │ ◄───────────────── │ ─────────────────────────────────────►  │
    │     (email+SMS)    │                    │   10. Notification │
    │                    │                    │                    │
    │                    │                    │                    │
    │ ═══ LESSON HAPPENS ═══                  │                    │
    │                    │                    │                    │
    │                    │ 11. Teacher marks  │                    │
    │                    │ ◄────────────────────────────────────── │
    │                    │     complete       │                    │
    │                    │ 12. booking →      │                    │
    │                    │     completed      │                    │
    │                    │ 13. Queue payout   │                    │
    │                    │                    │                    │
    │                    │ ═══ WEEKLY PAYOUT CYCLE ═══             │ 
    │                    │ 14. Process batch  │                    │
    │                    │     payouts       ──────────────────►   │
    │                    │                    │   15. Funds        │
```

---

## 3. PayFast Integration

### 3.1 Configuration

```python
# .env
PAYFAST_MERCHANT_ID=10000100
PAYFAST_MERCHANT_KEY=46f0cd694...
PAYFAST_PASSPHRASE=your-secret-passphrase
PAYFAST_SANDBOX=true                    # false in production
PAYFAST_RETURN_URL=https://fundaconnect.co.za/parent
PAYFAST_CANCEL_URL=https://fundaconnect.co.za/parent
PAYFAST_NOTIFY_URL=https://api.fundaconnect.co.za/api/v1/bookings/payfast/itn
```

### 3.2 Payment Initiation

When a parent creates a booking, the API generates a PayFast payment request:

```python
import hashlib
import urllib.parse

def generate_payfast_payment(booking, parent):
    data = {
        "merchant_id": settings.PAYFAST_MERCHANT_ID,
        "merchant_key": settings.PAYFAST_MERCHANT_KEY,
        "return_url": f"{settings.PAYFAST_RETURN_URL}?booking_id={booking.id}",
        "cancel_url": f"{settings.PAYFAST_CANCEL_URL}?booking_id={booking.id}",
        "notify_url": settings.PAYFAST_NOTIFY_URL,
        "name_first": parent.user.first_name,
        "name_last": parent.user.last_name,
        "email_address": parent.user.email,
        "m_payment_id": str(booking.id),        # our internal reference
        "amount": f"{booking.lesson_rate_cents / 100:.2f}",
        "item_name": f"FundaConnect Lesson - {booking.booking_number}",
        "item_description": f"1hr lesson with {booking.teacher.user.first_name}",
        "custom_str1": str(booking.id),
        "custom_str2": str(booking.teacher_id),
    }
    
    # Generate signature but do not submit passphrase as a form field
    payload_string = urllib.parse.urlencode(data)
    if settings.PAYFAST_PASSPHRASE:
        payload_string += f"&passphrase={settings.PAYFAST_PASSPHRASE}"
    signature = hashlib.md5(payload_string.encode()).hexdigest()

    return {
        "payment_url": "https://sandbox.payfast.co.za/eng/process",
        "form_data": {
            **data,
            "signature": signature,
        },
    }
```

### 3.3 ITN (Instant Transaction Notification) Handler

PayFast sends a server-to-server POST to the `notify_url` when payment status changes.

```python
@router.post("/bookings/payfast/itn")
async def payfast_itn(request: Request):
    form_data = await request.form()
    data = dict(form_data)
    
    # Step 1: Validate signature
    if not validate_payfast_signature(data):
        logger.warning("Invalid PayFast signature", extra={"data": data})
        return Response(status_code=200)  # Always return 200 to PayFast
    
    # Step 2: Validate source IP (PayFast IP ranges)
    client_ip = request.client.host
    if not is_payfast_ip(client_ip):
        logger.warning("ITN from non-PayFast IP", extra={"ip": client_ip})
        return Response(status_code=200)
    
    # Step 3: Validate payment data against our records
    booking_id = data.get("m_payment_id")
    booking = await get_booking(booking_id)
    if not booking:
        logger.error("Booking not found for ITN", extra={"booking_id": booking_id})
        return Response(status_code=200)
    
    expected_amount = f"{booking.lesson_rate_cents / 100:.2f}"
    if data.get("amount_gross") != expected_amount:
        logger.error("Amount mismatch", extra={"expected": expected_amount, "received": data.get("amount_gross")})
        return Response(status_code=200)
    
    # Step 4: Validate with PayFast server
    if not await validate_with_payfast_server(data):
        logger.error("PayFast server validation failed")
        return Response(status_code=200)
    
    # Step 5: Process based on payment status
    payment_status = data.get("payment_status")
    if payment_status == "COMPLETE":
        await handle_payment_complete(booking, data)
    elif payment_status == "CANCELLED":
        await handle_payment_cancelled(booking, data)
    elif payment_status == "FAILED":
        await handle_payment_failed(booking, data)
    
    return Response(status_code=200)
```

### 3.4 PayFast IP Validation

```python
PAYFAST_IP_RANGES = [
    "197.97.145.144/28",    # 197.97.145.144 - 197.97.145.159
    "41.74.179.192/27",     # 41.74.179.192 - 41.74.179.223
]

# In sandbox mode, also allow:
PAYFAST_SANDBOX_IPS = [
    "197.97.145.144/28",
]
```

---

## 4. Commission & Pricing

### 4.1 Commission Calculation

```python
def calculate_commission(lesson_rate_cents: int, teacher_tier: str) -> dict:
    """Calculate platform commission based on teacher subscription tier."""
    rates = {
        "standard": 0.175,    # 17.5% for free-tier teachers
        "premium":  0.12,     # 12% for premium subscribers
    }
    
    commission_rate = rates.get(teacher_tier, 0.175)
    platform_fee = int(lesson_rate_cents * commission_rate)
    teacher_payout = lesson_rate_cents - platform_fee
    
    return {
        "lesson_rate_cents": lesson_rate_cents,
        "commission_rate": commission_rate,
        "platform_fee_cents": platform_fee,
        "teacher_payout_cents": teacher_payout,
    }
```

### 4.2 Example Breakdown

| Component | Standard Teacher | Premium Teacher |
|-----------|-----------------|-----------------|
| Lesson rate | R250.00 | R250.00 |
| Commission rate | 17.5% | 12% |
| Platform fee | R43.75 | R30.00 |
| Teacher receives | R206.25 | R220.00 |
| PayFast fee (~3.4%) | R8.50 | R8.50 |
| Net platform revenue | R35.25 | R21.50 |

*Note: PayFast fees are absorbed by the platform, not the teacher.*

---

## 5. Escrow & Payout Logic

### 5.1 Escrow Rules

| Event | Funds Status |
|-------|-------------|
| Payment completed | Held in platform account |
| Lesson completed (teacher marks) | Released for payout processing |
| Lesson cancelled by parent (>24hrs before) | Full refund to parent |
| Lesson cancelled by parent (<24hrs before) | 50% refund to parent; 50% to teacher |
| Lesson cancelled by teacher | Full refund to parent |
| No-show by parent | Teacher receives full payout |
| No-show by teacher | Full refund to parent; teacher flagged |
| Dispute raised | Held pending admin resolution |

### 5.2 Weekly Payout Cycle

```
Every Monday at 06:00 SAST:
1. Query all bookings with status = 'completed' AND payout not yet processed
2. Group by teacher
3. For each teacher:
   a. Sum teacher_payout_cents for all eligible bookings
   b. Create teacher_payout record
   c. Initiate bank transfer (via PayFast split payment or manual EFT)
   d. Update payout status
   e. Send payout confirmation email to teacher
4. Log all payout activity for audit
```

### 5.3 Minimum Payout Threshold

- Minimum payout: R100.00
- If a teacher's accumulated earnings are below R100, the payout rolls over to the next cycle
- Teachers can view their pending balance at any time

---

## 6. Refund Processing

```python
async def process_refund(booking_id: UUID, refund_type: str):
    """
    refund_type: 'full' | 'partial_50'
    """
    booking = await get_booking(booking_id)
    payment = await get_payment_for_booking(booking_id)
    
    if refund_type == "full":
        refund_amount = payment.amount_cents
    elif refund_type == "partial_50":
        refund_amount = payment.amount_cents // 2
    
    # PayFast refund API call
    refund_result = await payfast_refund(
        payment_id=payment.gateway_payment_id,
        amount=refund_amount / 100
    )
    
    # Record refund
    await create_refund_record(
        payment_id=payment.id,
        amount_cents=refund_amount,
        gateway_reference=refund_result["reference"]
    )
    
    # Update payment status
    if refund_type == "full":
        payment.status = "refunded"
    else:
        payment.status = "partially_refunded"
    
    await save(payment)
```

---

## 7. Subscription Billing (Future Scope)

This section refers to optional platform membership products, not recurring lesson billing. Recurring lessons themselves currently use the prepaid weekly series model described above.

### 7.1 Teacher Premium Subscription

- **Amount:** R199–R499/month (tiered)
- **Method:** Future payment design decision if premium memberships are introduced; not implemented today
- **Trial:** 14-day free trial for new teachers
- **Cancellation:** Effective at end of current billing period

### 7.2 Parent FundaConnect Plus

- **Amount:** R99/month
- **Method:** Future payment design decision if a parent membership product is introduced; not implemented today
- **Benefits:** Progress tracking, portfolio tools, priority booking
- **Cancellation:** Immediate, pro-rated refund option

---

## 8. Financial Reporting

The platform generates the following reports:

| Report | Frequency | Contents |
|--------|-----------|----------|
| Daily revenue summary | Daily | Total bookings, revenue, refunds, net |
| Teacher payout report | Weekly | Per-teacher payout amounts, booking details |
| Monthly financial statement | Monthly | Revenue, costs, commissions, refunds, net income |
| VAT report | Monthly | Taxable revenue, VAT collected (when applicable) |
| Annual tax report | Annually | Full-year financial summary for SARS |
