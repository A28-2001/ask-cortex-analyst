with source as (
    select * from {{ source('raw', 'raw_subscription_events') }}
)

select
    event_id,
    event_date,
    date_trunc('month', event_date)::date as event_month,
    customer_id,
    segment,
    event_type,
    mrr_amount,
    contract_value
from source
