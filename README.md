# GoalIntel AI v5 — daily history and win/loss charts

## Added in v5
- Dedicated page for day before yesterday, yesterday, and today with daily wins/losses charts.
- Daily result entry form and CSV export.
- Separate next-day predictions page.
- Rolling seven-day fixture scanner.
- Daily results stored in `goalintel_results.csv` on the server's working directory when writable.

## Current limitations
- User must enter prediction results to populate charts; the app cannot reconstruct past picks that were never tracked.
- Next-day page lists fixtures, but does not fabricate picks without verified data and a validated market-specific model.
- Live football fixtures/scores require a private API-Football key and provider quota.
- Ice hockey and basketball need their own connected provider/data sources.
- Poisson goal probabilities are baseline estimates and not calibrated. The 80% filter is not a guarantee of actual 80% accuracy.

## Run
`pip install -r requirements.txt`
Set `API_FOOTBALL_KEY` privately, then run `streamlit run app.py`.
