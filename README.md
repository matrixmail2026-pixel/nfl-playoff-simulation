# NFL Playoff Simulation

A live-data NFL playoff model using the NFLMeta API to generate a provisional playoff field and simulate the postseason using a composite rating model.

## Features
- Fetches standings from NFLMeta
- Builds a 7-team provisional playoff field per conference
- Collects games for playoff teams
- Computes offensive and defensive EPA features
- Derives roster-based trench mass
- Simulates the playoff tree with logistic win probabilities
- Saves input data as CSV for auditability

## Donation Support
If you'd like to support this project, donations are appreciated:

- **Bitcoin**: bc1qachvftqjaayz7hn6y94gtc53xdtlvn9av8gy30
- **Litecoin**: ltc1qauxdduzemfrth5pyq8lmzj3ecf3jpfm5s8n863

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/matrixmail2026-pixel/nfl-playoff-simulation.git
cd nfl-playoff-simulation
```

### 2. Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set your API key
**Linux/macOS:**
```bash
export NFLMETA_API_KEY="your_key_here"
```

**Windows PowerShell:**
```powershell
$env:NFLMETA_API_KEY="your_key_here"
```

### 5. Run the model
```bash
python nfl_playoff_engine.py
```

## Model Components

### Composite Rating Formula
```
Rating = 0.40 * EPA_pass_off
       + 0.25 * EPA_pass_def
       + 0.15 * EPA_rush_off
       + 0.10 * Trench_Mass
       - 0.05 * Narrative_Adjustment
```

### Data Sources
- **EPA Stats**: Play-by-play expected points added from NFLMeta
- **Trench Mass**: Roster weight differential between OL and DL
- **Narrative**: Base multiplier (0.0, customizable)

## Simulation Pipeline

1. **Build Provisional Playoff Field** — Top 7 teams per conference by wins
2. **Collect EPA Data** — Play-by-play stats for all games involving playoff teams
3. **Calculate Features** — Pass/rush/defense EPA and trench mass
4. **Compute Ratings** — Weighted composite score per team
5. **Simulate Bracket** — Monte Carlo playoff bracket with logistic win probabilities

## Output

The simulation generates:
- Console output with full bracket results
- `nfl_2026_api_model_input.csv` — Full feature dataset
- Seed progression through Wild Card → Divisional → Conference → Super Bowl

## Notes
- NFLMeta free plan is rate-limited; this client respects the 20 requests/minute threshold
- The model is a live-data version of the original rating framework
- The playoff field is provisional and uses current standings to create a 7-team field per conference
- Donations welcome — see Donation Support above

## License
Creative Commons Attribution 4.0 International (CC BY 4.0)

See LICENSE file for details.
