# Vault - Pokemon TCG Portfolio Tracker

<div align="center">

![Vault Logo](https://img.shields.io/badge/Vault-Pokemon%20TCG-yellow?style=for-the-badge&logo=pokemon&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-green?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-orange?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)

### Track your Pokemon TCG collection's value with real-time pricing and AI-powered financial analytics

[Features](#features) | [Quick Start](#quick-start) | [Screenshots](#screenshots) | [Documentation](#documentation)

</div>

---

## Why Vault?

Pokemon TCG collecting has become a serious investment for many. Whether you're tracking a handful of chase cards or managing a large collection, knowing your portfolio's real value matters. **Vault** gives you the financial tools to:

- See your collection's **total market value** update in real-time
- Track **daily price movements** across your holdings
- Calculate **profit & loss** with cost basis tracking
- Identify **concentration risk** in overweight positions
- Get **AI-powered insights** on when to take profits or cut losses
- Monitor **top gainers and losers** in your portfolio

---

## Screenshots

<div align="center">

### Dashboard Overview
![Dashboard](screenshots/dashboard.png)

*Glassmorphism UI with animated backgrounds, real-time portfolio value, and P&L tracking*

</div>

---

## Features

### Modern Dashboard (v2.0)
- **Glassmorphism UI** with animated gradient backgrounds
- **Responsive design** - optimized for desktop, tablet, and mobile
- **Dark theme** with purple accent colors
- **Smooth animations** for polished user experience
- **Top Movers section** - see gainers and losers at a glance

### AI-Powered Insights
- **Portfolio Health Score** - overall portfolio assessment (0-100)
- **Market Momentum** - track if your holdings are rising or falling
- **Profit Taking Alerts** - notifications when items are up 50%+
- **Loss Review Warnings** - flags items down 25%+ for review
- **Concentration Risk** - alerts when top 5 holdings exceed 50%
- **Cost Tracking Reminders** - prompts to add missing cost basis

### Portfolio Management
- Import collections from **Collectr CSV exports**
- Real-time price fetching from **Pokemon TCG API**
- Track **cards** and **sealed products** separately
- Store **price history** for trend analysis
- **Editable cost basis** with auto-save functionality

### Financial Analytics
- **Total portfolio value** with daily change tracking
- **P&L calculation** - enter cost basis to see actual returns
- **Composition breakdown** - cards vs sealed visualization
- **Top holdings** with percentage allocation
- **Best/worst performers** by P&L percentage

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.10+** | Backend runtime |
| **Flask** | Web framework |
| **SQLite** | Embedded database |
| **Tailwind CSS** | UI styling |
| **Chart.js** | Data visualization |
| **Pokemon TCG API** | Market price data |
| **Gunicorn** | Production WSGI server |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/PryceHedrick/vault.git
cd vault

# Install dependencies
pip install -e .

# Import your collection (from Collectr CSV export)
vault import your_collection.csv

# Fetch current market prices
vault update

# Launch the dashboard
vault web
```

Open **http://localhost:5000** in your browser.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `vault import <csv>` | Import collection from Collectr CSV |
| `vault update` | Refresh prices from Pokemon TCG API |
| `vault summary` | Display portfolio summary in terminal |
| `vault list` | List all items with current prices |
| `vault web` | Launch web dashboard |
| `vault export` | Export collection to CSV |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/api/analysis` | GET | Portfolio analysis JSON |
| `/api/items` | GET | All items with prices |
| `/api/items/<id>/cost` | POST | Update item cost basis |
| `/api/items/<id>/history` | GET | Price history for item |

---

## What's New in v2.0

- Completely redesigned UI with glassmorphism and animated backgrounds
- Top Movers section showing gainers and losers
- Enhanced AI insights with market momentum tracking
- Improved mobile responsiveness with optimized layouts
- Portfolio health scoring with actionable recommendations
- Better visual hierarchy with gradient text and glow effects
- Smoother animations with staggered entry effects

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built for Pokemon TCG collectors who take their portfolio seriously**

[Pryce Hedrick](https://github.com/PryceHedrick) | [Pryceless Solutions](https://prycehedrick.com)

</div>
