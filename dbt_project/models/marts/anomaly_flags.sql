with base as (
    select * from {{ ref('mrr_movements') }}
),

with_rolling_stats as (
    select
        month,
        new_mrr,
        expansion_mrr,
        contraction_mrr,
        churn_mrr,
        net_new_mrr,
        ending_mrr,
        net_revenue_retention_pct,

        -- Rolling 6-month average and stddev (using prior months only, not current)
        avg(net_new_mrr)    over (order by month rows between 6 preceding and 1 preceding) as net_mrr_avg,
        stddev(net_new_mrr) over (order by month rows between 6 preceding and 1 preceding) as net_mrr_std,

        avg(churn_mrr)      over (order by month rows between 6 preceding and 1 preceding) as churn_avg,
        stddev(churn_mrr)   over (order by month rows between 6 preceding and 1 preceding) as churn_std,

        avg(expansion_mrr)  over (order by month rows between 6 preceding and 1 preceding) as expansion_avg,
        stddev(expansion_mrr) over (order by month rows between 6 preceding and 1 preceding) as expansion_std,

        avg(new_mrr)        over (order by month rows between 6 preceding and 1 preceding) as new_mrr_avg,
        stddev(new_mrr)     over (order by month rows between 6 preceding and 1 preceding) as new_mrr_std,

        avg(contraction_mrr) over (order by month rows between 6 preceding and 1 preceding) as contraction_avg,
        stddev(contraction_mrr) over (order by month rows between 6 preceding and 1 preceding) as contraction_std

    from base
),

flagged as (
    select
        month,
        new_mrr,
        expansion_mrr,
        contraction_mrr,
        churn_mrr,
        net_new_mrr,
        ending_mrr,
        net_revenue_retention_pct,

        -- Z-scores (null if not enough history or zero stddev)
        case when net_mrr_std > 0
             then round((net_new_mrr - net_mrr_avg) / net_mrr_std, 2) end     as net_mrr_z_score,
        case when churn_std > 0
             then round((churn_mrr - churn_avg) / churn_std, 2) end           as churn_z_score,
        case when expansion_std > 0
             then round((expansion_mrr - expansion_avg) / expansion_std, 2) end as expansion_z_score,
        case when new_mrr_std > 0
             then round((new_mrr - new_mrr_avg) / new_mrr_std, 2) end         as new_mrr_z_score,
        case when contraction_std > 0
             then round((contraction_mrr - contraction_avg) / contraction_std, 2) end as contraction_z_score,

        -- Anomaly flags (2σ threshold)
        (net_mrr_std    > 0 and abs(net_new_mrr    - net_mrr_avg)    > 2 * net_mrr_std)    as net_mrr_anomaly,
        (churn_std      > 0 and abs(churn_mrr      - churn_avg)      > 2 * churn_std)      as churn_anomaly,
        (expansion_std  > 0 and abs(expansion_mrr  - expansion_avg)  > 2 * expansion_std)  as expansion_anomaly,
        (new_mrr_std    > 0 and abs(new_mrr        - new_mrr_avg)    > 2 * new_mrr_std)    as new_mrr_anomaly,
        (contraction_std > 0 and abs(contraction_mrr - contraction_avg) > 2 * contraction_std) as contraction_anomaly

    from with_rolling_stats
    where net_mrr_avg is not null  -- need at least 1 prior month of history
),

final as (
    select
        *,
        (coalesce(net_mrr_anomaly, false)::int +
         coalesce(churn_anomaly, false)::int +
         coalesce(expansion_anomaly, false)::int +
         coalesce(new_mrr_anomaly, false)::int +
         coalesce(contraction_anomaly, false)::int)                     as total_anomalies,
        case when coalesce(net_mrr_anomaly, false)
                  or coalesce(churn_anomaly, false)
                  or coalesce(expansion_anomaly, false)
                  or coalesce(new_mrr_anomaly, false)
                  or coalesce(contraction_anomaly, false)
             then 'flagged' else 'normal' end                           as anomaly_status
    from flagged
)

select * from final
order by month
