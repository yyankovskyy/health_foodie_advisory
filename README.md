# Healthy Foodie Diet Advisor

**Integrated MVP — Dietologist, Preference Analyst, Cook Agent, and Master Orchestrator**  
Project documentation consolidated from the original starter README, Dietologist upgrade notes, Master/Preference upgrade notes, and receipt-data QA notes (20 November 2026).

## Overview

Healthy Foodie is a **local Streamlit + Python demonstration** for discovering recipes using pre-reviewed **synthetic** clinician instructions, user-specified preferences, cooking time, portion count, illustrative food budgets, and weak taste signals from curated grocery receipts. The application's filtering and rules are deterministic; an optional Superlinked-hosted text-generation model produces cooking explanations **only after** the recipe engine has identified candidates.

**Not a medical or food-allergy safety system.** Recipe ingredient summaries are incomplete, cross-contact is unverified, and all demo recipe nutrient and cost figures are unverified estimates. Do not interpret a recommendation as a prescription, diagnosis, nutrition-label verification, or allergy-safe certification. Real patient medical records, real-time receipt ingestion, and payment identifiers are out of scope.

## Architecture and responsibilities

| Component | Current module | Responsibility and boundaries |
|---|---|---|
| Master Orchestrator (E) | `master_agent.py` | Calls the Dietologist, Preference Analyst, and Cook Agent in sequence; returns recommendations, reports, and an execution trace; blocks requests with unreviewed/invalid clinician instructions |
| Dietologist Agent (C) | `dietologist_agent.py` | Reads and validates *pre-reviewed synthetic* clinician instructions, maintains sources and daily/per-meal scope, identifies conflicts/uncertainty; **never invents dietary limits** |
| Preference Analyst (B) | `preference_agent.py` | Analyzes manually curated, deduplicated medium/high-confidence receipt tags; treats them as weak preference hypotheses that users may select or dismiss; never infers allergies or clinical needs |
| Cook Agent (D) | `cook_agent.py`, `engine.py` | Deterministically excludes identified restricted ingredients and applies budget/time filters; ranks eligible recipes, provides original source links and cautions; optionally generates a cooking explanation via Superlinked |
| Interface (F) | `app.py` | Streamlit controls, clinician-instruction summary, receipt preference controls, results, explanation button, and Master Agent trace |
| Verification | `verify_workflow.py`, `tests/` | Offline integration demonstration and automated tests. External API connectivity scripts are run separately |

**Execution order:** Streamlit input → Master → Dietologist validation → user-controlled Preference Analyst → Cook/engine eligibility and ranking → results and warnings → optional Superlinked-generated explanation.

Clinical/allergy exclusions and user budget/time requirements always take precedence over preference ranking or generated prose. The optional LLM is not permitted to change eligibility, medical thresholds, or existing warnings.

## Project layout

```text
Healthy_Foodie/
├── app.py
├── master_agent.py
├── dietologist_agent.py
├── preference_agent.py
├── cook_agent.py
├── engine.py
├── verify_workflow.py
├── requirements.txt
├── README.md                         # This consolidated documentation
├── data/
│   ├── profiles.json
│   ├── recipes_demo.json
│   ├── receipts_curated.json          # Canonical receipt fixture
│   ├── receipt_curated.json           # Compatibility copy
│   └── receipts_demo.json            # Compatibility copy
└── tests/
    ├── test_engine.py
    ├── test_receipt_data_quality.py
    ├── test_dietologist_agent.py
    ├── test_preference_agent.py
    ├── test_master_agent.py
    ├── test_cook_agent_contract.py
    └── test_app_smoke.py
```

Your local project may also contain `tests/test_arcee.py` and `tests/test_superlinked.py`, which make **live external API calls** and should not run as ordinary offline unit tests. File inventory reflects the integrated upgrade, not the initial starter ZIP.

## Installation and first run (macOS)

From the project folder used for local development:

```bash
cd ~/Desktop/HealthyFoodieDietAdvisor/DesignImplementation/VersionO/Healthy_Foodie
source .venv_healthy_foodie/bin/activate
python -m pip install -r requirements.txt
```

If you do **not** have an existing virtual environment, create one using Python 3.11:

```bash
python3.11 -m venv .venv_healthy_foodie
source .venv_healthy_foodie/bin/activate
python -m pip install -r requirements.txt
```

If the requirements file still contains only the original Streamlit/Pytest dependencies, install the packages used by the optional hosted model integration:

```bash
python -m pip install openai python-dotenv
```

To install an upgrade over an **older starter project**, back up the working application files first, then extract the appropriate upgrade ZIP into the project root. The Master/Preference upgrade expects that `dietologist_agent.py` from the earlier Dietologist upgrade is already present. Do not overwrite your curated `data/` files or `.env` while upgrading.

```bash
mkdir -p backups
cp app.py engine.py cook_agent.py backups/
# If upgrading from an older version, extract the appropriate upgrade ZIP here.
```

### Optional Superlinked text generation

The verified working model in local testing was `Qwen/Qwen3.5-4B`. It belongs to **GENERATE**, not EXTRACT/Docling. Superlinked chat needs a valid account/key, available credits, and a chat-capable model. A working offline recommender does **not** require this service.

To configure credentials only for the current shell:

```bash
read -s SIE_API_KEY
export SIE_API_KEY
export SIE_MODEL="Qwen/Qwen3.5-4B"
python -c "import os; print('Superlinked key configured:', bool(os.getenv('SIE_API_KEY')))"
```

Paste the API key at the `read -s` prompt; it is not echoed. **Never commit or share the key.** Environment variables exported in a shell disappear when that shell ends.

Alternatively create a local `.env` (requires `python-dotenv`, and the installed Cook Agent implementation that loads it):

```dotenv
SIE_API_KEY=<your-private-key>
SIE_MODEL=Qwen/Qwen3.5-4B
```

Ensure `.gitignore` contains `.env`. The one-line terminal `os.getenv` check does not automatically read `.env`; `cook_agent.py` can load it when configured for `python-dotenv`. Use only synthetic, nonsensitive recipe descriptions, demo figures, selected preference tags, and previously displayed cautions in model requests—**not** medical records, raw receipt lines, payment details, or profile diagnoses.

### Start Streamlit

```bash
python -m streamlit run app.py
```

Open the `http://localhost:<port>` URL printed by Streamlit. The app may choose a port other than 8501 if that port is already occupied. To rerun after code changes, save the file and use the Streamlit menu's **Rerun** control, or stop the terminal server with Ctrl+C and restart.

## Automated and manual verification

Check syntax and run the **offline** suite:

```bash
python -m py_compile app.py engine.py cook_agent.py dietologist_agent.py preference_agent.py master_agent.py
python -m pytest -q --ignore=tests/test_arcee.py --ignore=tests/test_superlinked.py
python verify_workflow.py
```

The external connection checks, if retained, can be invoked manually:

```bash
python tests/test_superlinked.py
# Run the Arcee connectivity script only if its key/model access is configured.
```

The historical integrated-upgrade verification reported **48 tests passing in its development environment**. Your actual count depends on which test files are installed; successful offline tests do **not** prove the live Superlinked account, credentials, network, or Streamlit UI works. `test_app_smoke.py` uses a stubbed UI and the Cook Agent contract test mocks the outbound model request.

### Suggested Streamlit acceptance sequence

1. **Guest**: Select meal `Any`, $12 total demo budget, 45 minutes; recommendations should appear with no LLM call or invented clinician limits.
2. **Receipt preferences**: Enable sample purchases, select only `vegetables` and review the evidence panel: **13 source receipt records, 12 distinct purchases, 1 ignored duplicate payment slip**. Do not interpret purchases as allergies, nutrition facts, or definite preferences.
3. **Manual preference**: Select `soup` as a positive preference; matched soups should receive transparent ranking points, without bypassing eligibility filters.
4. **Allergy exclusion**: Select synthetic `peanut` allergy; recipes with identified peanuts (e.g. Pad Thai) remain excluded even when noodles are preferred. Incomplete ingredient and cross-contact information stays explicitly unverified.
5. **Dietologist—Marina**: Show simulated **2,000 mg sodium/day**; **do not** convert this to an invented per-meal allowance or infer additional kidney-diet rules.
6. **Dietologist—Daniel**: Show the simulated **approximately 60 g carbohydrate/meal** target. Compare the estimate for **one recipe serving** with the per-meal target, not the carbohydrate total for all household portions. GERD triggers are individual cautions, not universal prohibitions.
7. **Master trace**: Inspect the execution trace showing Dietologist, Preference Analyst, Cook Agent, and Master stages; invalid or conflicting clinician instructions must halt recommendations for review.
8. **Cook explanation**: Click **Ask Cook Agent for cooking advice**. The optional Superlinked explanation must not claim to have read the original publisher URL, invent nutrition values, or override the displayed allergen/medical warnings. Change profiles and confirm stale explanations are not shown for the new context.
9. **Offline resilience**: Repeat basic recommendations with no `SIE_API_KEY` configured; the model explanation may be unavailable, but deterministic eligibility and ranking should continue working.

## Key programmatic interfaces

### Dietologist profile review

```python
from dietologist_agent import review_profile, review_recipe

report = review_profile(profile, additional_synthetic_allergies=["peanut"])
if not report["ready"]:
    print(report["review_errors"])  # Stop, don't silently drop invalid orders.
else:
    profile_for_engine = report["effective_profile"]
    # Generate candidate(s) through the deterministic recommendation engine.
    # notes = review_recipe(candidate["recipe"], report)
```

A report may contain `hard_avoid`, `daily_limits`, `meal_limits`, `personal_triggers`, `guideline_ids`, `uncertainties`, `clinical_flags`, source provenance, `review_errors`, and the normalized engine profile. Source linkage is to **synthetic profile instructions**, not to independently verified external clinical guidelines. The `guideline_ids` collection is empty in this MVP.

### Master Agent orchestration

```python
from engine import load_json
from master_agent import run_meal_request

profile = next(
    p for p in load_json("profiles.json") if p["id"] == "guest"
)
plan = run_meal_request(
    profile=profile,
    recipes=load_json("recipes_demo.json"),
    receipts=load_json("receipts_curated.json"),
    meal_type="dinner",
    budget_usd=12.0,
    max_minutes=45,
    servings=1,
    use_receipt_hints=True,
    selected_receipt_tags=["vegetables"],
    manual_preference_tags=["soup"],
)
if plan["status"] != "ready":
    print(plan["dietologist"]["review_errors"])
else:
    print([r["recipe"]["name"] for r in plan["recommendations"]["candidates"]])
```

**Preference ranking is additive, never a safety override.** The optional `preference_weights`, `preference_score`, and `matched_preference_tags` make ranking transparent. Only terms present in the recipe vocabulary can affect ranking: the curated receipts contain `sushi`/`japanese`, for example, but these do not automatically influence the 10 demo recipes without matching recipe tags. Do not silently equate unrelated tags and cuisines.

## Data sources, provenance, and limitations

### Synthetic profiles

`data/profiles.json` contains manually normalized synthetic patient facts (including Marina Ellis and Daniel Ortiz) and a Guest option. They are **not** the output of an automated real-world medical-record extraction pipeline. Clinical limits are those supplied in pre-reviewed synthetic instructions, not generated by the model. Unknown and conflicting instructions require review rather than assumptions.

### Recipe fixtures

`data/recipes_demo.json` contains **10 demo recipes** with cuisine tags, *partial* ingredient summaries, original publisher links, and test-only numeric fields. All demo prices, calorie amounts, carbohydrates, and sodium values are **illustrative and not source verified**; they are not current grocery quotations or measured nutrient composition. Full ingredient lists, quantities, allergens, cross-contact, serving sizes, and nutrition need source-level verification before any real dietary use. Consult publisher attribution and licensing before production ingestion.

### Receipt dataset — consolidated QA documentation

| Inventory | Count / location |
|---|---|
| Original receipt images | `IMG_2557.jpeg`–`IMG_2559.jpeg` (3 image records; 2 purchases) |
| Additional receipt images | `IMG_2563.jpeg`–`IMG_2572.jpeg` (10 image records; 10 purchases) |
| Image records | **13** |
| Distinct purchases | **12** |
| Duplicate | Frankfurt card/payment slip, linked with `duplicate_of`, not an additional purchase |
| Food line entries | **131**, including repeated products on separate receipt lines |
| Canonical app data | `data/receipts_curated.json` |
| Compatibility data | `data/receipt_curated.json` and `data/receipts_demo.json` (equivalent copies in the original data package) |

The receipts are curated, de-identified transcriptions of photographs, not current price feeds. Interpret fields conservatively:

- `price` denotes a **historic printed extended line amount** in its native `currency` (USD or EUR), not a unit price, recipe portion cost, or current estimate. `quantity`, `quantity_unit`, and `unit_price` may be expressed on different bases (each, pounds, etc.).
- `food_purchase_subtotal_identified` sums only food lines with confirmed visible prices and may be less than `receipt_total`. Unknown prices, dates, receipt totals, item identity, and quantities remain **`null`**, not guessed.
- Distinct receipts are kept separate; repeated purchase lines within one transaction are retained rather than deduplicated by product name.
- Deposits, nonfood entries, tender/payment metadata and illegible lines are excluded or explicitly noted. The Frankfurt payment slip is not counted as another purchase.
- Receipt `interpretation`, `category`, and `tags` are **manual guesses/classifications at documented confidence levels**, not verified ingredients, allergy/cross-contact information, medical facts, or proof of personal taste. Low-confidence items must not drive clinical screening.
- `IMG_2565.jpeg` (Trader Joe's) was folded/partly obscured/cropped. Its `receipt_total` is unknown and its identified food subtotal covers **visible priced items only**.
- The curated JSON excludes payment-card digits, benefit balances, trace IDs and other account identifiers. **Original source receipt photos are not bundled with the app package.**

Receipt data QA tests cover the 13 image IDs, 12 distinct purchases, the duplicate payment slip, equivalent JSON entry points, subtotal arithmetic, missing-value handling, and 131 food lines.

### Reference material

- User-provided *Healthy Foodie — Lean MVP Design and Phased Implementation* (architecture and incremental milestones).
- User-provided *Evidence-Based Nutrition Guidance* (US/EU/UK, 19 November 2026); external evidence citations remain in that source document and are **not automatically enforced** by the app.
- User-provided *World Cuisines & Recipes* guide (18 November 2026), recipe items 1–45 and publisher links; only 10 illustrative records are in the current app fixture.
- Synthetic Marina Ellis and Daniel Ortiz patient-summary PDFs.
- Receipt image sources listed in the inventory above.
- [USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide/) — possible later source for verified nutrient composition (API key required).
- [Streamlit file uploader documentation](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader) — possible later controlled upload workflow.

## Development milestones and current scope

| Milestone | Status in integrated MVP |
|---|---|
| R1 — Local UI, synthetic fixtures, preliminary recipe filtering | Implemented |
| R2 — Clinician instruction display, allergy exclusions and uncertainty flags | Implemented at demo level; not clinically validated |
| R3 — Budget/time screening, publisher links, curated receipt taste hints | Implemented; recipe costs are demo estimates |
| R4 — Optional LLM explanation | Implemented via Superlinked GENERATE when configured; no LLM safety authority |
| R5 — Uploads, evidence extraction and production ingestion | **Not implemented** |
| Dietologist (C) + Preference Analyst (B) + Master (E) orchestration | Implemented as deterministic local pipeline |
| Semantic embeddings / external SCORE reranking | Not part of this integrated release |

**Still out of scope:** live OCR, genuine patient-record processing, personalized medical prescriptions, verified nutrient calculation, current shopping prices, a production food-allergen database, accounts and consent management, live payments, automated cloud deployment and production privacy/security controls. A single receipt item labeled “vegan” must not determine a persistent dietary identity.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `KeyError: 'id'` on recipe | Demo recipes may not have `id`; use an existing stable `source_url`/name fallback and a hashed Streamlit button key |
| `KeyError: 'SIE_API_KEY'` or key absent after restarting terminal | Export key again in the launching shell, or configure `.env` with `python-dotenv`; do not reveal it in logs |
| Superlinked 503 using `docling` for chat | Docling is an **EXTRACT** model, not chat-capable GENERATE; use an available chat model such as the locally tested `Qwen/Qwen3.5-4B` |
| Pytest fails while collecting `test_arcee.py` | Run offline tests with `--ignore=tests/test_arcee.py --ignore=tests/test_superlinked.py`, or rename live connectivity scripts to avoid Pytest discovery |
| Browser shows old Streamlit values or no response | Check Streamlit's terminal process and browser connection, then rerun/restart the server; inspect any terminal exception |
| Unexpected nutrition restriction | Check the synthetic profile's **explicit** scope and supporting source; never convert a daily restriction into a new per-meal prescription |

## Rollback after an upgrade

If you backed up the integrated application before installing the newest module set:

```bash
cp backups/app.py app.py
cp backups/engine.py engine.py
cp backups/cook_agent.py cook_agent.py
```

New modules may remain on disk unused until you re-enable the upgraded app. Keep a versioned backup of the working project and do not store private API keys in version control.

---

**Documentation policy:** Maintain this `README.md` as the single entry point. Future updates should modify the relevant sections above instead of creating another standalone `README_*_UPGRADE.md`. Keep `data/` JSON provenance and tests synchronized with any factual inventory changes.
