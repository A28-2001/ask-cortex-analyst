with recent_usage as (
    -- Last 3 months of usage signals per customer
    select
        customer_id,
        avg(login_count)       as avg_logins,
        avg(feature_adoption)  as avg_feature_adoption,
        avg(support_tickets)   as avg_support_tickets,
        avg(nps_score)         as avg_nps,
        avg(days_since_login)  as avg_days_since_login
    from {{ ref('stg_usage_signals') }}
    where signal_month >= (
        select dateadd(month, -3, max(signal_month))
        from {{ ref('stg_usage_signals') }}
    )
    group by 1
),

recent_revenue as (
    -- Last 6 months of revenue signals per customer
    select
        customer_id,
        sum(case when event_type = 'expansion'   then mrr_amount      else 0 end) as expansion_mrr,
        sum(case when event_type = 'contraction' then abs(mrr_amount) else 0 end) as contraction_mrr,
        max(case when event_type = 'churn'       then 1               else 0 end) as has_churned,
        -- Most recent non-churn MRR as a proxy for current MRR
        max(case when event_type in ('new', 'expansion', 'reactivation') then mrr_amount end) as peak_mrr
    from {{ ref('stg_subscription_events') }}
    where event_month >= (
        select dateadd(month, -6, max(event_month))
        from {{ ref('stg_subscription_events') }}
    )
    group by 1
),

scored as (
    select
        c.customer_id,
        c.company_name,
        c.segment,
        c.cohort_month,
        c.industry,
        c.sales_rep,

        -- Engagement (0-100): feature adoption rate
        round(coalesce(u.avg_feature_adoption, 50), 1)                                     as engagement_score,

        -- Recency (0-100): penalise days since last login (cap at 20 days = score 0)
        round(greatest(0, 100 - coalesce(u.avg_days_since_login, 15) * 5.0), 1)            as recency_score,

        -- Support burden (0-100): fewer tickets = healthier
        round(greatest(0, 100 - coalesce(u.avg_support_tickets, 1) * 20), 1)               as support_score,

        -- NPS (0-100): normalise 0-10 NPS to 0-100
        round(coalesce(u.avg_nps / 10.0 * 100, 50), 1)                                     as nps_score_normalized,

        -- Revenue health (0-100): penalise net contraction
        round(greatest(0,
            100 - coalesce(r.contraction_mrr / nullif(r.expansion_mrr + r.peak_mrr, 0), 0) * 50
        ), 1)                                                                                as revenue_health_score,

        coalesce(r.peak_mrr, 0)                                                             as current_mrr,
        r.expansion_mrr,
        r.contraction_mrr,
        coalesce(r.has_churned, 0)                                                          as has_churned
    from {{ ref('stg_customers') }} c
    left join recent_usage   u on c.customer_id = u.customer_id
    left join recent_revenue r on c.customer_id = r.customer_id
    where coalesce(r.has_churned, 0) = 0  -- active customers only
),

final as (
    select
        customer_id,
        company_name,
        segment,
        cohort_month,
        industry,
        sales_rep,
        engagement_score,
        recency_score,
        support_score,
        nps_score_normalized,
        revenue_health_score,
        current_mrr,
        expansion_mrr,
        contraction_mrr,
        round(
            engagement_score    * 0.25 +
            recency_score       * 0.25 +
            support_score       * 0.15 +
            nps_score_normalized * 0.15 +
            revenue_health_score * 0.20,
            1
        )                                                                   as composite_health_score,
        case
            when (engagement_score * 0.25 + recency_score * 0.25 + support_score * 0.15 +
                  nps_score_normalized * 0.15 + revenue_health_score * 0.20) >= 75 then 'healthy'
            when (engagement_score * 0.25 + recency_score * 0.25 + support_score * 0.15 +
                  nps_score_normalized * 0.15 + revenue_health_score * 0.20) >= 65 then 'at_risk'
            else 'critical'
        end                                                                 as health_status
    from scored
)

select * from final
order by composite_health_score asc  -- most at-risk first
