# Installation Guide

## Requirements
- Python 3.9 or higher
- pip (Python package manager)
- git

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/matrixmail2026-pixel/nfl-playoff-simulation.git
cd nfl-playoff-simulation
```

### 2. Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set your NFLMeta API key

**Linux / macOS:**
```bash
export NFLMETA_API_KEY="your_api_key_here"
```

**Windows (PowerShell):**
```powershell
$env:NFLMETA_API_KEY="your_api_key_here"
```

**Windows (CMD):**
```cmd
set NFLMETA_API_KEY=your_api_key_here
```

### 5. Run the simulation
```bash
python nfl_playoff_engine.py
```

The script will:
1. Fetch current standings from NFLMeta
2. Build a 7-team playoff field per conference
3. Collect play-by-play data for all playoff teams
4. Calculate EPA and trench mass features
5. Compute composite ratings
6. Simulate the entire playoff bracket
7. Output results to console and `nfl_2026_api_model_input.csv`

## Troubleshooting

### API Key Error
If you get an error about `NFLMETA_API_KEY`:
1. Ensure you have a valid API key from NFLMeta
2. Check that the environment variable is set correctly
3. Try running without the `.venv` first to isolate the issue

### Network Issues
If you see rate-limit warnings or timeouts:
1. The script respects a 3.1-second request interval (20 requests/minute)
2. This is the default for NFLMeta's free tier
3. The script will automatically retry on 429 (rate limit) errors
4. Be patient; first run may take 5-10 minutes

### Missing Dependencies
If you get import errors:
```bash
pip install --upgrade -r requirements.txt
```

## Support

For issues with this project, please create an issue on GitHub.

For NFLMeta API documentation, visit: https://nflmeta.org

## Donations

If this project is useful to you, consider donating:

- **Bitcoin**: bc1qachvftqjaayz7hn6y94gtc53xdtlvn9av8gy30
- **Litecoin**: ltc1qauxdduzemfrth5pyq8lmzj3ecf3jpfm5s8n863

## License

This project is licensed under Creative Commons Attribution 4.0 International (CC BY 4.0).
See LICENSE file for details.
