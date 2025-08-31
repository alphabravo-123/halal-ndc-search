# HalalMed — DailyMed Ingredients + Halal Marking (Prototype)

This is a minimal proof-of-concept that pulls drug labels from **DailyMed**,
extracts **Active** and **Inactive** ingredients, and marks them with a basic
Halal status (`likely_halal`, `likely_haram`, `needs_verification`, `unknown`).

> ⚠️ Disclaimer: This is NOT a certification tool and does not provide religious rulings.
> It uses simple keyword heuristics for education and triage. Always verify with
> certified Halal authorities and the product's manufacturer.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the backend
uvicorn app.main:app --reload --port 8000
```

Open `frontend/index.html` in your browser, or run any static server
from the `frontend` folder (e.g., `python -m http.server 5173`), then set
the API base URL in the page if needed (defaults to `http://localhost:8000`).

## API

- `GET /api/search?name=<drug name>` → returns candidate SPL setids & titles
- `GET /api/label/<setid>` → returns parsed active & inactive ingredients + halal status

## Notes

- Parsing uses DailyMed v2 REST endpoints and SPL XML. It looks for the
  LOINC code **51727-6** (INACTIVE INGREDIENT SECTION) when present, and
  falls back to title-based matching if needed.
- Active ingredients are pulled from common sections and structured blocks
  where available.

