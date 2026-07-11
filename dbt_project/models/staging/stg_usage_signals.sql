with source as (
    select * from {{ source('raw', 'raw_usage_signals') }}
)

select
    signal_id,
    customer_id,
    signal_month,
    login_count,
    feature_adoption,
    support_tickets,
    nps_score,
    days_since_login
from source
