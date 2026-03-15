import { ShippingCalculator } from "@/components/shipping/ShippingCalculator";

export default function ShippingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Shipment Calculator</h2>
        <p className="text-muted-foreground">
          Compare Amazon FBA vs Local fulfillment costs based on volumetric weight.
        </p>
      </div>

      <ShippingCalculator />
    </div>
  );
}
