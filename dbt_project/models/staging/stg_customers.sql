with source as (
    select * from {{ source('raw', 'raw_customers') }}
)

select
    customer_id,
    company_name,
    segment,
    acquisition_date,
    date_trunc('month', acquisition_date)::date as cohort_month,
    industry,
    sales_rep
from source
