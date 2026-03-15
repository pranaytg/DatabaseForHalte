-- Phase 1: Database Schema (PostgreSQL) modifications for SellerBoard features

-- Add ad_spend to orders
ALTER TABLE orders ADD COLUMN IF NOT EXISTS ad_spend numeric DEFAULT 0.00;

-- Add supply chain info to sku_master
ALTER TABLE sku_master ADD COLUMN IF NOT EXISTS manufacturing_lead_time integer DEFAULT 15;
ALTER TABLE sku_master ADD COLUMN IF NOT EXISTS transit_time integer DEFAULT 15;

-- Create COGS_Batches for FIFO logic
CREATE TABLE IF NOT EXISTS cogs_batches (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sku varchar REFERENCES sku_master(sku) ON DELETE CASCADE,
    batch_date timestamptz DEFAULT now(),
    unit_cost numeric NOT NULL,
    quantity_received integer NOT NULL,
    quantity_sold integer DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Index for FIFO retrieval
CREATE INDEX IF NOT EXISTS idx_cogs_batches_sku_date ON cogs_batches (sku, batch_date);

-- Note: When running this in Supabase, make sure your schema matches these table names.
