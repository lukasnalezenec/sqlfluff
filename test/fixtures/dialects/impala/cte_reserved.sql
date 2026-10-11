WITH hold AS (
    SELECT 1 AS id
),
treat AS (
    SELECT 2 AS id
)
SELECT id;

WITH `hold` AS (
    SELECT 1 AS id
)
SELECT id FROM `hold`;
