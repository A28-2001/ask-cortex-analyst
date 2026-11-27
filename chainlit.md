## About the data

The warehouse behind this demo holds **synthetic** subscription data for a made-up SaaS company: 500 customers from January 2025 to June 2026, modelled in dbt on Snowflake.

You can ask about:

- **MRR**, month by month and broken into new, expansion, contraction, churn and reactivation, company-wide or by segment (SMB, mid-market, enterprise)
- **Retention**, by acquisition cohort, and net revenue retention
- **Customer health**, a 0 to 100 score per active customer, with who is at risk
- **Anomalies**, months where churn, new or net MRR moved unusually against the previous six months

Questions go to Snowflake Cortex Analyst, which writes SQL against a documented semantic model. Every answer shows that SQL, so you can check it. A question the data can't answer, such as a forecast or a metric it doesn't define, gets a refusal and a reason instead of a guess.

**Recorded answers.** While the warehouse is offline, or once the demo's daily live budget is used up, answers come from the real responses recorded during the evaluation, and each one is labelled that way.

[Read the write-up](/) / [Code and eval data](https://github.com/A28-2001/ask-cortex-analyst)
