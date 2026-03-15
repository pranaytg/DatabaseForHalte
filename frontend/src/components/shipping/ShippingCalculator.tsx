"use client";

import { useState, useEffect } from "react";
import { createClient } from "@supabase/supabase-js";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Calculator,
  Package,
  Truck,
  Loader2,
  CheckCircle2,
  Plane,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);

interface SkuOption {
  sku: string;
  product_name: string;
  length_cm: number | null;
  width_cm: number | null;
  height_cm: number | null;
  weight_kg: number | null;
}

type Zone = "LOCAL" | "REGIONAL" | "NATIONAL";

interface CarrierCost {
  id: string;
  carrier: string;
  zone: Zone;
  billableWeight: number;
  baseCost: number;
  slabCost: number;
  fsc: number;
  gst: number;
  total: number;
  icon: React.ReactNode;
}

function calculateBillableWeight(
  actualKg: number,
  lengthCm: number,
  widthCm: number,
  heightCm: number,
) {
  const volumetricWeight = (lengthCm * widthCm * heightCm) / 5000;
  let rawBillable = Math.max(actualKg, volumetricWeight);

  let billableWeight = Math.ceil(rawBillable * 2) / 2;
  if (billableWeight < 0.5 && billableWeight > 0) billableWeight = 0.5;

  return { volumetricWeight, billableWeight };
}

function determineZone(originPincode: string, destPincode: string): Zone {
  const o = originPincode.trim();
  const d = destPincode.trim();
  if (!o || !d) return "NATIONAL";
  if (o === d) return "LOCAL";
  if (o.substring(0, 2) === d.substring(0, 2)) return "REGIONAL";
  return "NATIONAL";
}

function calculateShippingCosts(
  billableWeight: number,
  zone: Zone,
): CarrierCost[] {
  if (billableWeight <= 0) return [];

  const slabs = Math.max(1, Math.ceil(billableWeight / 0.5));
  const additionalSlabs = slabs - 1;

  const fbaRates = {
    LOCAL: { base: 43, add: 16 },
    REGIONAL: { base: 54.5, add: 21 },
    NATIONAL: { base: 76, add: 26 },
  };
  const fbaBase = fbaRates[zone].base;
  const fbaSlab = fbaRates[zone].add * additionalSlabs;
  const fbaFsc = 0;
  const fbaPreTax = fbaBase + fbaSlab + fbaFsc;
  const fbaGst = fbaPreTax * 0.18;
  const fbaTotal = Math.round(fbaPreTax + fbaGst);

  const delRates = {
    LOCAL: { base: 40, add: 40 },
    REGIONAL: { base: 50, add: 45 },
    NATIONAL: { base: 65, add: 55 },
  };
  const delBase = delRates[zone].base;
  const delSlab = delRates[zone].add * additionalSlabs;
  const delFsc = (delBase + delSlab) * 0.1;
  const delPreTax = delBase + delSlab + delFsc;
  const delGst = delPreTax * 0.18;
  const delTotal = Math.round(delPreTax + delGst);

  const bdRates = {
    LOCAL: { base: 55, add: 50 },
    REGIONAL: { base: 65, add: 60 },
    NATIONAL: { base: 85, add: 80 },
  };
  const bdBase = bdRates[zone].base;
  const bdSlab = bdRates[zone].add * additionalSlabs;
  const bdFsc = (bdBase + bdSlab) * 0.15;
  const bdPreTax = bdBase + bdSlab + bdFsc;
  const bdGst = bdPreTax * 0.18;
  const bdTotal = Math.round(bdPreTax + bdGst);

  return [
    {
      id: "fba",
      carrier: "Amazon FBA",
      zone,
      billableWeight,
      baseCost: fbaBase,
      slabCost: fbaSlab,
      fsc: fbaFsc,
      gst: fbaGst,
      total: fbaTotal,
      icon: <Package className="h-5 w-5" />,
    },
    {
      id: "delhivery",
      carrier: "Delhivery",
      zone,
      billableWeight,
      baseCost: delBase,
      slabCost: delSlab,
      fsc: delFsc,
      gst: delGst,
      total: delTotal,
      icon: <Truck className="h-5 w-5" />,
    },
    {
      id: "bluedart",
      carrier: "Blue Dart",
      zone,
      billableWeight,
      baseCost: bdBase,
      slabCost: bdSlab,
      fsc: bdFsc,
      gst: bdGst,
      total: bdTotal,
      icon: <Plane className="h-5 w-5" />,
    },
  ];
}

export function ShippingCalculator() {
  const [skus, setSkus] = useState<SkuOption[]>([]);
  const [isLoadingSkus, setIsLoadingSkus] = useState(true);

  const [selectedSku, setSelectedSku] = useState<string>("");
  const [originPincode, setOriginPincode] = useState("110001");
  const [destPincode, setDestPincode] = useState("");

  const [dimensions, setDimensions] = useState({
    length: 0,
    width: 0,
    height: 0,
    weight: 0,
  });
  const [isCalculated, setIsCalculated] = useState(false);

  useEffect(() => {
    async function fetchSkus() {
      setIsLoadingSkus(true);
      try {
        const { data, error } = await supabase
          .from("sku_master")
          .select(
            "sku, product_name, length_cm, width_cm, height_cm, weight_kg",
          )
          .order("sku");

        if (data) {
          setSkus(data as SkuOption[]);
        } else if (error) {
          console.error("Error fetching SKUs:", error);
        }
      } catch (err) {
        console.error("Failed to fetch SKUs:", err);
      } finally {
        setIsLoadingSkus(false);
      }
    }
    fetchSkus();
  }, []);

  const handleSkuSelect = (skuId: string | null) => {
    if (!skuId) return;
    setSelectedSku(skuId);
    setIsCalculated(false);

    const sku = skus.find((s) => s.sku === skuId);
    if (sku) {
      setDimensions({
        length: sku.length_cm || 0,
        width: sku.width_cm || 0,
        height: sku.height_cm || 0,
        weight: sku.weight_kg || 0,
      });
    }
  };

  const handleDimensionChange = (
    field: keyof typeof dimensions,
    value: string,
  ) => {
    setIsCalculated(false);
    const parsed = parseFloat(value);
    setDimensions((prev) => ({
      ...prev,
      [field]: isNaN(parsed) ? 0 : parsed,
    }));
  };

  const { volumetricWeight, billableWeight } = calculateBillableWeight(
    dimensions.weight,
    dimensions.length,
    dimensions.width,
    dimensions.height,
  );

  const currentZone = determineZone(originPincode, destPincode);
  const costs = calculateShippingCosts(billableWeight, currentZone);
  const minCost = costs.length > 0 ? Math.min(...costs.map((c) => c.total)) : 0;

  const handleCalculate = () => {
    if (!destPincode) {
      alert("Please enter a destination pincode.");
      return;
    }
    setIsCalculated(true);
  };

  return (
    <div className="grid gap-6 md:grid-cols-12">
      <Card className="md:col-span-5 self-start">
        <CardHeader>
          <CardTitle>Shipment Details</CardTitle>
          <CardDescription>
            Select a product to auto-fill its dimensions or enter manually.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Origin Pincode</Label>
              <Input
                placeholder="e.g. 110001"
                value={originPincode}
                onChange={(e) => {
                  setOriginPincode(e.target.value);
                  setIsCalculated(false);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Destination Pincode</Label>
              <Input
                placeholder="e.g. 400001"
                value={destPincode}
                onChange={(e) => {
                  setDestPincode(e.target.value);
                  setIsCalculated(false);
                }}
              />
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <Label>Select Product (SKU)</Label>
            <Select
              value={selectedSku}
              onValueChange={handleSkuSelect}
              disabled={isLoadingSkus}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={
                    isLoadingSkus ? "Loading SKUs..." : "Select a product..."
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {skus.map((sku) => (
                  <SelectItem key={sku.sku} value={sku.sku}>
                    {sku.sku} - {sku.product_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {isLoadingSkus && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" /> Fetching catalog...
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Actual Weight (kg)</Label>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={dimensions.weight || ""}
                onChange={(e) =>
                  handleDimensionChange("weight", e.target.value)
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Length (cm)</Label>
              <Input
                type="number"
                min="0"
                step="0.1"
                value={dimensions.length || ""}
                onChange={(e) =>
                  handleDimensionChange("length", e.target.value)
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Width (cm)</Label>
              <Input
                type="number"
                min="0"
                step="0.1"
                value={dimensions.width || ""}
                onChange={(e) => handleDimensionChange("width", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Height (cm)</Label>
              <Input
                type="number"
                min="0"
                step="0.1"
                value={dimensions.height || ""}
                onChange={(e) =>
                  handleDimensionChange("height", e.target.value)
                }
              />
            </div>
          </div>

          <div className="rounded-lg border border-border/50 bg-muted/50 p-4 space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Volumetric Weight:</span>
              <span className="font-medium">
                {volumetricWeight.toFixed(3)} kg
              </span>
            </div>
            <div className="flex justify-between items-center text-sm font-semibold border-t border-border/50 pt-2 text-primary">
              <span>Billable Weight (Slab):</span>
              <span>{billableWeight.toFixed(2)} kg</span>
            </div>
          </div>

          <Button
            className="w-full"
            onClick={handleCalculate}
            disabled={
              (!selectedSku &&
                dimensions.weight === 0 &&
                dimensions.length === 0) ||
              !destPincode
            }
          >
            <Calculator className="mr-2 h-4 w-4" />
            Calculate Shipping Costs
          </Button>
        </CardContent>
      </Card>

      <div className="md:col-span-7">
        {!isCalculated ? (
          <Card className="flex h-full min-h-[400px] flex-col items-center justify-center border-dashed bg-muted/30 text-muted-foreground">
            <Package className="mb-4 h-12 w-12 opacity-20" />
            <p>Select a product and destination to view shipping estimates.</p>
          </Card>
        ) : (
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-semibold tracking-tight">
                Shipping Estimates
              </h3>
              <div className="flex items-center gap-3 mt-1">
                <Badge variant="secondary" className="text-xs font-normal">
                  Zone: {currentZone}
                </Badge>
                <Badge variant="secondary" className="text-xs font-normal">
                  Billable: {billableWeight.toFixed(2)} kg
                </Badge>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-1 xl:grid-cols-2">
              {costs.map((cost) => {
                const isWinner = cost.total === minCost;
                return (
                  <Card
                    key={cost.id}
                    className={`relative overflow-hidden transition-all ${
                      isWinner
                        ? "border-emerald-500/50 bg-emerald-500/5 shadow-[0_0_15px_-3px_rgba(16,185,129,0.15)] xl:col-span-2"
                        : ""
                    }`}
                  >
                    {isWinner && (
                      <div className="absolute top-0 right-0 rounded-bl-lg bg-emerald-500 px-3 py-1 text-xs font-medium text-white flex items-center gap-1 shadow-sm pb-1.5 pl-3.5 border-l border-b border-emerald-600/20">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Most Profitable
                      </div>
                    )}
                    <CardHeader className={isWinner ? "pb-2" : ""}>
                      <CardTitle className="flex items-center gap-2 text-lg">
                        {cost.icon}
                        {cost.carrier}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold tracking-tight mb-4">
                        {formatCurrency(cost.total)}
                      </div>

                      <div
                        className={`space-y-2 text-sm text-muted-foreground border-t border-border/50 pt-4 ${isWinner ? "grid grid-cols-2 gap-x-6 gap-y-3 space-y-0 text-xs" : ""}`}
                      >
                        <div className="flex justify-between items-center">
                          <span>Base Fee (First 0.5kg):</span>
                          <span>{formatCurrency(cost.baseCost)}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span>Additional Slabs:</span>
                          <span>{formatCurrency(cost.slabCost)}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span>Fuel Surcharge:</span>
                          <span>{formatCurrency(cost.fsc)}</span>
                        </div>
                        <div
                          className={`flex justify-between items-center font-medium pt-1 border-t border-border/30 text-foreground ${isWinner ? "col-span-2 mt-1" : ""}`}
                        >
                          <span>Subtotal + 18% GST:</span>
                          <span>{formatCurrency(cost.total)}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
