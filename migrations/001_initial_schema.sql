-- =============================================================================
-- Amazon SP-API Dashboard — Complete PostgreSQL Schema for Supabase
-- =============================================================================
-- Run this in your Supabase SQL Editor to bootstrap the entire database.
-- Safe to re-run: uses DROP IF EXISTS + CREATE.
-- =============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for text search on product names


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. SKU MASTER — Single source of truth for all products
-- ─────────────────────────────────────────────────────────────────────────────
-- Merges the old `skus` + `cost_prices` tables.
-- COGS lives here. Editable via the dashboard.

DROP TABLE IF EXISTS financial_events CASCADE;
DROP TABLE IF EXISTS order_items       CASCADE;
DROP TABLE IF EXISTS orders            CASCADE;
DROP TABLE IF EXISTS warehouse_inventory CASCADE;
DROP TABLE IF EXISTS sku_master        CASCADE;

CREATE TABLE sku_master (
    sku             VARCHAR(100)   PRIMARY KEY,
    asin            VARCHAR(20),
    fnsku           VARCHAR(20),                           -- FBA-specific identifier
    product_name    VARCHAR(500)   NOT NULL,
    category        VARCHAR(200),
    brand           VARCHAR(200),

    -- Cost of Goods Sold (editable from dashboard)
    cogs            DECIMAL(10,2)  NOT NULL DEFAULT 0.00,

    -- Dimensions — used by the shipment calculator
    weight_kg       DECIMAL(8,3),
    length_cm       DECIMAL(8,2),
    width_cm        DECIMAL(8,2),
    height_cm       DECIMAL(8,2),

    -- Selling channel info
    channel         VARCHAR(20)    NOT NULL DEFAULT 'amazon'
                        CHECK (channel IN ('amazon', 'website', 'both')),
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,

    -- Housekeeping
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  sku_master       IS 'Single source of truth for products. COGS lives here.';
COMMENT ON COLUMN sku_master.cogs  IS 'Cost of Goods Sold per unit, used in profitability calculations.';
COMMENT ON COLUMN sku_master.fnsku IS 'Fulfillment Network SKU assigned by Amazon FBA.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. WAREHOUSE INVENTORY — FBA vs FBM stock per warehouse
-- ─────────────────────────────────────────────────────────────────────────────
-- Populated by SP-API FbaInventory endpoint.
-- One row per (sku × warehouse × fulfillment_channel).

CREATE TABLE warehouse_inventory (
    id                      UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku                     VARCHAR(100)   NOT NULL REFERENCES sku_master(sku) ON DELETE CASCADE,
    warehouse_id            VARCHAR(50)    NOT NULL,          -- Amazon FC code or custom warehouse name
    warehouse_name          VARCHAR(200),

    fulfillment_channel     VARCHAR(10)    NOT NULL DEFAULT 'FBA'
                                CHECK (fulfillment_channel IN ('FBA', 'FBM')),

    -- Stock quantities
    quantity                INTEGER        NOT NULL DEFAULT 0,
    quantity_inbound        INTEGER        NOT NULL DEFAULT 0,  -- in-transit to FC
    quantity_reserved       INTEGER        NOT NULL DEFAULT 0,  -- reserved for orders
    quantity_unfulfillable  INTEGER        NOT NULL DEFAULT 0,  -- damaged / customer-returns

    -- Restock intelligence
    days_of_supply          INTEGER,                           -- estimated days until stock-out
    reorder_point           INTEGER,                           -- trigger restock when qty ≤ this

    -- Sync metadata
    last_synced_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    -- Prevent duplicate rows for the same SKU in the same warehouse+channel
    UNIQUE (sku, warehouse_id, fulfillment_channel)
);

COMMENT ON TABLE warehouse_inventory IS 'Per-warehouse FBA/FBM inventory. Synced from SP-API FbaInventory.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. ORDERS — Revamped order headers
-- ─────────────────────────────────────────────────────────────────────────────
-- Populated by SP-API OrdersV0.

CREATE TABLE orders (
    id                      UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    amazon_order_id         VARCHAR(50)    NOT NULL UNIQUE,
    purchase_date           TIMESTAMPTZ    NOT NULL,
    last_update_date        TIMESTAMPTZ,

    order_status            VARCHAR(30)    NOT NULL DEFAULT 'Pending'
                                CHECK (order_status IN (
                                    'Pending', 'Unshipped', 'PartiallyShipped',
                                    'Shipped', 'Canceled', 'Returned'
                                )),

    fulfillment_channel     VARCHAR(10)    NOT NULL DEFAULT 'FBA'
                                CHECK (fulfillment_channel IN ('FBA', 'FBM')),

    -- Financials (order level)
    order_total             DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    currency_code           VARCHAR(5)     NOT NULL DEFAULT 'INR',

    -- Buyer info (minimal, SP-API restricted)
    buyer_name              VARCHAR(255),
    shipping_city           VARCHAR(100),
    shipping_state          VARCHAR(100),
    shipping_postal_code    VARCHAR(20),

    -- Marketplace
    marketplace_id          VARCHAR(20)    NOT NULL DEFAULT 'A21TJRUUN4KGV', -- Amazon.in
    sales_channel           VARCHAR(100)   DEFAULT 'Amazon.in',

    -- Housekeeping
    created_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE orders IS 'Order headers from SP-API OrdersV0. One row per Amazon order.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. ORDER ITEMS — Line items with fee breakdown
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE order_items (
    id                      UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id                UUID           NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku                     VARCHAR(100)   NOT NULL REFERENCES sku_master(sku) ON DELETE SET NULL,
    asin                    VARCHAR(20),
    order_item_id           VARCHAR(50),   -- Amazon's OrderItemId

    -- Quantities & pricing
    quantity                INTEGER        NOT NULL DEFAULT 1,
    item_price              DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    item_tax                DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    shipping_price          DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    shipping_tax            DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    promotion_discount      DECIMAL(10,2)  NOT NULL DEFAULT 0.00,

    -- Amazon fees (populated from financial_events or SP-API estimates)
    referral_fee            DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    fba_fee                 DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    commission              DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    other_fees              DECIMAL(10,2)  NOT NULL DEFAULT 0.00,

    -- COGS snapshot — written at sync time from sku_master.cogs
    -- This preserves historical profitability even if COGS changes later.
    unit_cogs               DECIMAL(10,2)  NOT NULL DEFAULT 0.00,

    -- Calculated fields (updated by backend when COGS or fees change)
    cogs_total              DECIMAL(10,2)  NOT NULL DEFAULT 0.00,  -- unit_cogs × quantity
    shipping_cost           DECIMAL(10,2)  NOT NULL DEFAULT 0.00,  -- actual outbound shipping cost
    total_fees              DECIMAL(10,2)  NOT NULL DEFAULT 0.00,  -- sum of all Amazon fees
    net_profit              DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    profit_margin_pct       DECIMAL(5,2)   NOT NULL DEFAULT 0.00,

    created_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  order_items             IS 'Order line items with full fee breakdown for profitability.';
COMMENT ON COLUMN order_items.unit_cogs   IS 'Snapshot of sku_master.cogs at sync time. Used for historical profitability.';
COMMENT ON COLUMN order_items.net_profit  IS '= item_price - total_fees - shipping_cost - (unit_cogs × quantity)';


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. FINANCIAL EVENTS — Raw Amazon fee data from FinancesV0
-- ─────────────────────────────────────────────────────────────────────────────
-- Stores every fee line item from the SP-API ListFinancialEvents response.
-- Used to reconcile and update the fee columns in order_items.

CREATE TABLE financial_events (
    id                      UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    amazon_order_id         VARCHAR(50)    NOT NULL,
    order_item_id           VARCHAR(50),

    event_type              VARCHAR(50)    NOT NULL,          -- e.g. 'ShipmentEvent', 'RefundEvent'
    fee_type                VARCHAR(100),                     -- e.g. 'FBAPerUnitFulfillmentFee', 'Commission'
    fee_description         VARCHAR(300),

    -- Money
    amount                  DECIMAL(12,2)  NOT NULL DEFAULT 0.00,
    currency_code           VARCHAR(5)     NOT NULL DEFAULT 'INR',

    -- Timing
    posted_date             TIMESTAMPTZ    NOT NULL,

    -- Sync metadata
    raw_event_json          JSONB,                           -- full SP-API response for debugging
    created_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    -- Prevent duplicate ingestion
    UNIQUE (amazon_order_id, order_item_id, fee_type, posted_date)
);

COMMENT ON TABLE financial_events IS 'Raw financial events from SP-API FinancesV0. Used for fee reconciliation.';


-- =============================================================================
-- INDEXES — Optimized for dashboard queries
-- =============================================================================

-- sku_master
CREATE INDEX idx_sku_master_asin       ON sku_master(asin);
CREATE INDEX idx_sku_master_channel    ON sku_master(channel);
CREATE INDEX idx_sku_master_active     ON sku_master(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_sku_master_name_trgm  ON sku_master USING gin(product_name gin_trgm_ops);

-- warehouse_inventory
CREATE INDEX idx_wh_inv_sku            ON warehouse_inventory(sku);
CREATE INDEX idx_wh_inv_channel        ON warehouse_inventory(fulfillment_channel);
CREATE INDEX idx_wh_inv_warehouse      ON warehouse_inventory(warehouse_id);
CREATE INDEX idx_wh_inv_last_synced    ON warehouse_inventory(last_synced_at DESC);

-- orders
CREATE INDEX idx_orders_purchase_date  ON orders(purchase_date DESC);
CREATE INDEX idx_orders_status         ON orders(order_status);
CREATE INDEX idx_orders_channel        ON orders(fulfillment_channel);
CREATE INDEX idx_orders_marketplace    ON orders(marketplace_id);

-- order_items
CREATE INDEX idx_oi_order_id           ON order_items(order_id);
CREATE INDEX idx_oi_sku                ON order_items(sku);

-- financial_events
CREATE INDEX idx_fe_order_id           ON financial_events(amazon_order_id);
CREATE INDEX idx_fe_posted_date        ON financial_events(posted_date DESC);
CREATE INDEX idx_fe_event_type         ON financial_events(event_type);


-- =============================================================================
-- TRIGGERS — Auto-update `updated_at` timestamps
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sku_master_updated
    BEFORE UPDATE ON sku_master
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_wh_inv_updated
    BEFORE UPDATE ON warehouse_inventory
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_orders_updated
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_order_items_updated
    BEFORE UPDATE ON order_items
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();


-- =============================================================================
-- VIEW — Pre-computed SKU Profitability (used by the dashboard)
-- =============================================================================
-- Aggregates order_items to give per-SKU revenue, fees, COGS, and net profit.

CREATE OR REPLACE VIEW v_sku_profitability AS
SELECT
    sm.sku,
    sm.asin,
    sm.product_name,
    sm.cogs                                         AS current_unit_cogs,
    sm.category,
    COALESCE(agg.total_quantity, 0)                  AS units_sold,
    COALESCE(agg.total_revenue, 0)                   AS total_revenue,
    COALESCE(agg.total_fees, 0)                      AS total_amazon_fees,
    COALESCE(agg.total_shipping_cost, 0)             AS total_shipping_cost,
    COALESCE(agg.total_cogs, 0)                      AS total_cogs,
    COALESCE(agg.total_net_profit, 0)                AS total_net_profit,
    CASE
        WHEN COALESCE(agg.total_revenue, 0) > 0
        THEN ROUND(COALESCE(agg.total_net_profit, 0) / agg.total_revenue * 100, 2)
        ELSE 0
    END                                              AS net_margin_pct,
    COALESCE(agg.order_count, 0)                     AS order_count
FROM sku_master sm
LEFT JOIN (
    -- Uses order_items.unit_cogs (snapshot at sync time), NOT sku_master.cogs
    SELECT
        oi.sku,
        SUM(oi.quantity)            AS total_quantity,
        SUM(oi.item_price)          AS total_revenue,
        SUM(oi.total_fees)          AS total_fees,
        SUM(oi.shipping_cost)       AS total_shipping_cost,
        SUM(oi.unit_cogs * oi.quantity) AS total_cogs,
        SUM(oi.item_price - oi.total_fees - oi.shipping_cost - (oi.unit_cogs * oi.quantity)) AS total_net_profit,
        COUNT(DISTINCT oi.order_id) AS order_count
    FROM order_items oi
    GROUP BY oi.sku
) agg ON agg.sku = sm.sku
WHERE sm.is_active = TRUE
ORDER BY COALESCE(agg.total_net_profit, 0) DESC;

COMMENT ON VIEW v_sku_profitability IS 'Per-SKU profitability summary: revenue - fees - shipping - COGS = net_profit.';


-- =============================================================================
-- VIEW — Order Profitability (per-order net profit)
-- =============================================================================

CREATE OR REPLACE VIEW v_order_profitability AS
SELECT
    o.id                AS order_id,
    o.amazon_order_id,
    o.purchase_date,
    o.order_status,
    o.fulfillment_channel,
    o.order_total,
    COALESCE(SUM(oi.item_price), 0)                                               AS line_item_revenue,
    COALESCE(SUM(oi.total_fees), 0)                                               AS total_fees,
    COALESCE(SUM(oi.shipping_cost), 0)                                            AS total_shipping_cost,
    COALESCE(SUM(oi.unit_cogs * oi.quantity), 0)                                  AS total_cogs,
    COALESCE(SUM(oi.item_price - oi.total_fees - oi.shipping_cost - (oi.unit_cogs * oi.quantity)), 0) AS net_profit,
    CASE
        WHEN COALESCE(SUM(oi.item_price), 0) > 0
        THEN ROUND(
            COALESCE(SUM(oi.item_price - oi.total_fees - oi.shipping_cost - (oi.unit_cogs * oi.quantity)), 0)
            / SUM(oi.item_price) * 100, 2
        )
        ELSE 0
    END                                                                           AS net_margin_pct
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, o.amazon_order_id, o.purchase_date, o.order_status,
         o.fulfillment_channel, o.order_total
ORDER BY o.purchase_date DESC;

COMMENT ON VIEW v_order_profitability IS 'Per-order profitability: aggregated line-item fees, COGS, and net profit.';


-- =============================================================================
-- VIEW — Warehouse Stock Summary (dashboard card)
-- =============================================================================

CREATE OR REPLACE VIEW v_warehouse_summary AS
SELECT
    wi.warehouse_id,
    wi.warehouse_name,
    wi.fulfillment_channel,
    COUNT(DISTINCT wi.sku)              AS sku_count,
    SUM(wi.quantity)                    AS total_available,
    SUM(wi.quantity_inbound)            AS total_inbound,
    SUM(wi.quantity_reserved)           AS total_reserved,
    SUM(wi.quantity_unfulfillable)      AS total_unfulfillable,
    MIN(wi.last_synced_at)              AS oldest_sync
FROM warehouse_inventory wi
GROUP BY wi.warehouse_id, wi.warehouse_name, wi.fulfillment_channel
ORDER BY wi.fulfillment_channel, wi.warehouse_id;

COMMENT ON VIEW v_warehouse_summary IS 'Aggregated inventory per warehouse for the dashboard overview.';


-- =============================================================================
-- ROW LEVEL SECURITY — Supabase standard
-- =============================================================================

ALTER TABLE sku_master           ENABLE ROW LEVEL SECURITY;
ALTER TABLE warehouse_inventory  ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders               ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_events     ENABLE ROW LEVEL SECURITY;

-- Service-role (backend) can do everything
CREATE POLICY "service_role_all" ON sku_master
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON warehouse_inventory
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON orders
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON order_items
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON financial_events
    FOR ALL USING (auth.role() = 'service_role');

-- Authenticated users get read-only access (for the frontend dashboard)
CREATE POLICY "authenticated_read" ON sku_master
    FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON warehouse_inventory
    FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON orders
    FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON order_items
    FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "authenticated_read" ON financial_events
    FOR SELECT USING (auth.role() = 'authenticated');

-- Authenticated users can update COGS in sku_master (dashboard editing)
CREATE POLICY "authenticated_update_cogs" ON sku_master
    FOR UPDATE USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');


-- =============================================================================
-- DONE — Schema ready for Phase 2 (SP-API Backend Integration)
-- =============================================================================
