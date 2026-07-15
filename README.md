# Ask Cortex Analyst

A natural-language data assistant built on Snowflake Cortex Analyst.

A text-to-SQL business intelligence assistant grounded by a Cortex
Analyst semantic model over a real SaaS subscription dataset (500
customers, 18 months): MRR, churn, cohort retention, customer health
scoring, and anomaly detection, migrated from an existing dbt project.

Ask a plain-English business question; the assistant translates it into
SQL against the semantic model, runs it, and returns the answer. No SQL
knowledge required, and every answer shows the exact query it ran.

## The finding, not just the build

The point of this project isn't "an AI chatbot for SQL." It's a
measured test of whether a semantic layer actually prevents the
hallucination and wrong-answer failure modes a naive text-to-SQL setup
has. Same 36-question benchmark, same rubric, run against both:

| | Naive baseline (raw schema, no semantic model) | Cortex Analyst (semantic model) |
|---|---|---|
| Accuracy | 65.3% | 100% |
| Guardrail correct-refusal rate | 50% | 100% |
| Hallucination rate | 16.7% | 0% |

Full results and methodology, including the specific failure modes
found and fixed along the way, are in `eval/`:
- `eval/rubric.md`: the scoring rubric, locked before any question ran
- `eval/phase4_results_summary.md`: Cortex Analyst eval + iteration history
- `eval/phase5_results_summary.md`: the baseline comparison
- `eval/phase6_results_summary.md`: adversarial stress test (false
  premises, jailbreak pressure, prompt injection)

## Project structure

- `dbt_project/`: the migrated dbt models (staging + marts) running on Snowflake
- `semantic_model/nl_assistant.yaml`: the Cortex Analyst semantic model
- `eval/`: rubric, question bank, ground truth, and results for every eval phase
- `chainlit_app/`: the landing page, chat interface, and FastAPI server
- `scripts/`: migration, eval harness, and Cortex Analyst client code

## Running locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-app.txt
cp .env.example .env  # fill in your own Snowflake + Groq credentials
uvicorn chainlit_app.server:app --port 8000
```

Then open http://localhost:8000 for the landing page, or
http://localhost:8000/chat for the assistant directly. (Use the full
`requirements.txt` instead if you also want to run the dbt migration or
the eval harness in `scripts/`.)

## Stack

Snowflake · Cortex Analyst · dbt · Chainlit · Groq (naive baseline) · Python
