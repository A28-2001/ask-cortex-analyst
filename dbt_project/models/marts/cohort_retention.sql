with customer_lifecycle as (
    -- Determine each customer's cohort month and churn month (if any)
    select
        c.customer_id,
        c.cohort_month,
        c.segment,
        min(case when e.event_type = 'churn' then e.event_month end) as churn_month
    from {{ ref('stg_customers') }} c
    left join {{ ref('stg_subscription_events') }} e
        on c.customer_id = e.customer_id
    group by c.customer_id, c.cohort_month, c.segment
),

cohort_sizes as (
    select
        cohort_month,
        count(distinct customer_id) as cohort_size
    from customer_lifecycle
    group by 1
),

-- All distinct months in the dataset
all_months as (
    select distinct event_month as month
    from {{ ref('stg_subscription_events') }}
),

-- Cross join each customer's cohort with every month from their cohort onwards
cohort_activity as (
    select
        cl.customer_id,
        cl.cohort_month,
        cl.segment,
        m.month                                                         as active_month,
        -- Customer is active if this month >= cohort_month and before churn (or never churned)
        case
            when m.month >= cl.cohort_month
             and (cl.churn_month is null or m.month < cl.churn_month)
            then 1 else 0
        end                                                             as is_active
    from customer_lifecycle cl
    cross join all_months m
    where m.month >= cl.cohort_month
),

retention_by_cohort as (
    select
        cohort_month,
        active_month,
        sum(is_active)                                                  as active_customers,
        datediff(month, cohort_month, active_month)                     as months_since_cohort
    from cohort_activity
    group by 1, 2
)

select
    r.cohort_month,
    r.active_month,
    r.months_since_cohort,
    cs.cohort_size,
    r.active_customers,
    round(r.active_customers::numeric / cs.cohort_size * 100, 1)       as retention_rate_pct
from retention_by_cohort r
join cohort_sizes cs on r.cohort_month = cs.cohort_month
order by r.cohort_month, r.active_month
