import { Suspense } from "react";
import type { Metadata } from "next";
import { PaymentReceiptPage } from "@/components/parent/payment-receipt-page";

export const metadata: Metadata = { title: "Payment Receipt" };

export default async function ParentPaymentReceiptRoute({
  params,
}: {
  params: Promise<{ paymentId: string }>;
}) {
  const { paymentId } = await params;

  return (
    <Suspense>
      <PaymentReceiptPage paymentId={paymentId} />
    </Suspense>
  );
}
