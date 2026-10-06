-- ============================================================
-- marina_analysis_queries.sql
-- Comparison queries for Blue Sky Marina competitor analysis.
--
-- Schema reminder:
--   facilities(facility_id, facility_name, is_own_business, total_capacity,
--              dry_storage_capacity, min_boat_length, max_boat_length,
--              services_raw, google_rating, google_review_count,
--              website, phone_number, address, size_covered_raw, ...)
--   pricing(pricing_id, facility_id, slip_price_min_monthly,
--           slip_price_max_monthly, slip_price_raw, storage_price_per_month,
--           storage_price_raw, launch_fee, launch_fee_raw, fuel_available)
--   reviews(review_id, facility_id, source, sentiment, theme, note)
--
-- Note: slip_price_min/max_monthly is NULL for Driftwood, Cruiser Haven,
-- and Holland Riverside on purpose -- their real pricing wasn't a clean
-- min-max range (an unverified estimate, a per-foot rate, and a single
-- flat number, respectively). Their exact text is in slip_price_raw.
-- Queries below that average or rank slip price will silently exclude
-- those 3 -- call that out explicitly in your write-up, don't let it look
-- like an accident.
-- ============================================================


-- 1. CAPACITY COMPARISON
-- Where does Blue Sky Marina's 125-slip capacity sit relative to competitors?
SELECT
    facility_name,
    total_capacity,
    dry_storage_capacity,
    CASE WHEN is_own_business = 1 THEN 'Blue Sky Marina (own)' ELSE 'Competitor' END AS role
FROM facilities
ORDER BY total_capacity DESC;


-- 2. PRICE PER SLIP (using the midpoint of each marina's price range)
-- A fairer comparison than raw price since slip prices vary by boat size.
-- Excludes the 3 marinas whose pricing wasn't a clean range (see note above).
SELECT
    f.facility_name,
    p.slip_price_min_monthly,
    p.slip_price_max_monthly,
    ROUND((p.slip_price_min_monthly + p.slip_price_max_monthly) / 2.0, 2) AS slip_price_midpoint,
    f.total_capacity
FROM facilities f
JOIN pricing p ON f.facility_id = p.facility_id
WHERE p.slip_price_min_monthly IS NOT NULL
ORDER BY slip_price_midpoint ASC;


-- 3. PRICE vs. GOOGLE RATING
-- Is a higher price associated with a higher rating, or is it noise?
-- Good input for a Tableau scatter plot (x = price midpoint, y = rating).
SELECT
    f.facility_name,
    ROUND((p.slip_price_min_monthly + p.slip_price_max_monthly) / 2.0, 2) AS slip_price_midpoint,
    f.google_rating,
    f.google_review_count
FROM facilities f
JOIN pricing p ON f.facility_id = p.facility_id
WHERE f.is_own_business = 0
ORDER BY slip_price_midpoint ASC;


-- 4. LAUNCH FEE COMPARISON
-- Raw text included since a few launch fees are tiered (weekday/weekend)
-- rather than a flat number.
SELECT
    facility_name,
    launch_fee,
    launch_fee_raw
FROM facilities f
JOIN pricing p ON f.facility_id = p.facility_id
WHERE f.is_own_business = 0
ORDER BY launch_fee ASC;


-- 5. STORAGE OPTIONS
-- Several competitors have NO dry storage at all -- if Lloyd's/Blue Sky's
-- 100-space dry storage capacity is a genuine differentiator, this query
-- is the evidence for that claim.
SELECT
    facility_name,
    storage_price_per_month,
    storage_price_raw,
    dry_storage_capacity
FROM facilities f
JOIN pricing p ON f.facility_id = p.facility_id
ORDER BY facility_name;


-- 6. TOP COMPLAINTS AND PRAISE, SIDE BY SIDE PER MARINA
-- Pulls the negative and positive review theme into one row per competitor,
-- for an easy-to-read positioning table (good for the Figma summary).
SELECT
    f.facility_name,
    f.google_rating,
    f.google_review_count,
    MAX(CASE WHEN r.sentiment = 'negative' THEN r.note END) AS top_complaint,
    MAX(CASE WHEN r.sentiment = 'positive' THEN r.note END) AS top_praise
FROM facilities f
LEFT JOIN reviews r ON f.facility_id = r.facility_id
WHERE f.is_own_business = 0
GROUP BY f.facility_id
ORDER BY f.google_rating DESC;


-- 7. RECURRING COMPLAINT THEMES ACROSS ALL COMPETITORS
-- Rough keyword scan across every complaint note -- useful for spotting a
-- market-wide gap (e.g. "if half these marinas get complained about for
-- bathrooms/security, that's a positioning opportunity for Blue Sky Marina").
-- SQLite has no regex by default, so this uses LIKE per keyword; add more
-- keywords as you notice patterns while reading the notes yourself.
SELECT
    f.facility_name,
    r.note AS complaint_text,
    CASE
        WHEN r.note LIKE '%bathroom%' OR r.note LIKE '%BATHROOM%' THEN 'bathrooms'
        WHEN r.note LIKE '%rude%' OR r.note LIKE '%Rude%' THEN 'staff/rudeness'
        WHEN r.note LIKE '%security%' OR r.note LIKE '%Security%' OR r.note LIKE '%cats%' THEN 'security'
        WHEN r.note LIKE '%dirty%' OR r.note LIKE '%Filthy%' OR r.note LIKE '%run down%' OR r.note LIKE '%Run down%' THEN 'cleanliness/condition'
        WHEN r.note LIKE '%charge extra%' OR r.note LIKE '%Charge extra%' THEN 'hidden fees'
        WHEN r.note LIKE '%support%' OR r.note LIKE '%assistance%' THEN 'poor support'
        ELSE 'other'
    END AS complaint_category
FROM facilities f
JOIN reviews r ON f.facility_id = r.facility_id
WHERE r.sentiment = 'negative' AND f.is_own_business = 0
ORDER BY complaint_category;


-- 8. MASTER SUMMARY VIEW
-- One row per competitor with the core metrics for pricing/positioning --
-- this is the table to export as CSV and import into Tableau if the
-- direct SQLite connector gives you trouble.
SELECT
    f.facility_name,
    f.address,
    f.total_capacity,
    f.dry_storage_capacity,
    f.google_rating,
    f.google_review_count,
    p.slip_price_min_monthly,
    p.slip_price_max_monthly,
    p.slip_price_raw,
    p.storage_price_raw,
    p.launch_fee_raw,
    p.fuel_available
FROM facilities f
LEFT JOIN pricing p ON f.facility_id = p.facility_id
ORDER BY f.is_own_business DESC, f.facility_name;
