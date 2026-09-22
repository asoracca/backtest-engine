WITH curve AS (
    SELECT row_number, equity,
           MAX(equity) OVER (ORDER BY row_number ROWS UNBOUNDED PRECEDING) AS peak
    FROM ledgers WHERE run_id = :run_id AND ledger = 'cash'
), costs AS (
    SELECT COALESCE(SUM(commission), 0) AS commission,
           COALESCE(SUM(slippage_cost), 0) AS slippage_cost,
           COUNT(*) AS fills
    FROM ledgers WHERE run_id = :run_id AND ledger = 'fills'
)
SELECT (SELECT equity FROM curve ORDER BY row_number DESC LIMIT 1) AS final_equity,
       (SELECT MIN(equity / peak - 1.0) FROM curve) AS max_drawdown,
       commission, slippage_cost, fills
FROM costs;
