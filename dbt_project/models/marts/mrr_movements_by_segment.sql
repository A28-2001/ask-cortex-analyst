with monthly_components as (
    select
        event_month                                                                    as month,
        segment,
        sum(case when event_type = 'new'         then mrr_amount  else 0 end)         as new_mrr,
        sum(case when event_type = 'expansion'   then mrr_amount  else 0 end)         as expansion_mrr,
        sum(case when event_type = 'contraction' then abs(mrr_amount) else 0 end)     as contraction_mrr,
        sum(case when event_type = 'churn'       then abs(mrr_amount) else 0 end)     as churn_mrr,
        sum(case when event_type = 'reactivation' then mrr_amount else 0 end)         as reactivation_mrr,
        count(distinct case when event_type = 'new'   then customer_id end)           as new_customers,
        count(distinct case when event_type = 'churn' then customer_id end)           as churned_customers
    from {{ ref('stg_subscription_events') }}
    group by 1, 2
),

with_net as (
    select
        *,
        new_mrr + expansion_mrr + reactivation_mrr - contraction_mrr - churn_mrr     as net_new_mrr
    from monthly_components
),

with_running_totals as (
    select
        month,
        segment,
        new_mrr,
        expansion_mrr,
        contraction_mrr,
        churn_mrr,
        reactivation_mrr,
        net_new_mrr,
        new_customers,
        churned_customers,
        -- Starting MRR = cumulative net MRR up to but not including this month, per segment
        coalesce(
            sum(net_new_mrr) over (partition by segment order by month rows between unbounded preceding and 1 preceding),
            0
        )                                                                              as starting_mrr,
        sum(net_new_mrr) over (partition by segment order by month)                    as ending_mrr
    from with_net
),

final as (
    select
        month,
        segment,
        round(starting_mrr, 2)                                                        as starting_mrr,
        round(new_mrr, 2)                                                             as new_mrr,
        round(expansion_mrr, 2)                                                       as expansion_mrr,
        round(contraction_mrr, 2)                                                     as contraction_mrr,
        round(churn_mrr, 2)                                                           as churn_mrr,
        round(reactivation_mrr, 2)                                                    as reactivation_mrr,
        round(net_new_mrr, 2)                                                         as net_new_mrr,
        round(ending_mrr, 2)                                                          as ending_mrr,
        new_customers,
        churned_customers,
        -- Net Revenue Retention: (ending MRR from existing customers) / starting MRR, per segment
        case
            when starting_mrr > 0
            then round((starting_mrr + expansion_mrr + reactivation_mrr - contraction_mrr - churn_mrr) / starting_mrr * 100, 1)
        end                                                                            as net_revenue_retention_pct
    from with_running_totals
)

select * from final
order by month, segment
