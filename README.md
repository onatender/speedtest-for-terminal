# speedtest-for-terminal

Minimal, colorful terminal speed test for Windows/macOS/Linux. Runs with Python, optionally builds to a single-file Windows EXE.

- Live, tasteful progress (spinners and stage updates)
- Clean final summary with colors
- JSON output for scripting

## Contents
- `speedtest_cli.py`: CLI application
- `requirements.txt`: Dependencies
- `dist/speedtest.exe`: Single-file Windows binary (after build)

## Requirements
- Python 3.9+

## Installation
```powershell
cd C:\path\speedtest
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
Run with colorful live progress (default duration 1s):
```powershell
python .\speedtest_cli.py
```

Options:
- `-t, --time <seconds>`: Duration for measurement (default: 1)
- `--download-only`: Run only download test
- `--upload-only`: Run only upload test
- `--json`: Print raw JSON (disables live progress)
- `--no-live`: Disable live progress, keep plain output
- `--no-secure`: Disable HTTPS to test endpoints (default: secure on)
- `-h, -help`: Show help

Examples:
```powershell
# 3-second only download
python .\speedtest_cli.py --download-only -t 3

# 3-second only upload
python .\speedtest_cli.py --upload-only -t 3

# JSON for scripting
python .\speedtest_cli.py --json > result.json

# Plain output without live spinner
python .\speedtest_cli.py --no-live
```

Example output:
```
Speedtest Results
==================
ISP       : Example ISP
IP        : 203.0.113.10
Location  : TR

Server    : Example Sponsor, Istanbul, TR
Latency   : 12.34 ms
Download  : 123.45 Mbps
Upload    : 45.67 Mbps
```

## Build Windows EXE (one-file)
```powershell
# from project root
.\.venv\Scripts\pyinstaller --noconfirm --onefile --console --name speedtest speedtest_cli.py
# output: dist\speedtest.exe
```

## License
MIT


