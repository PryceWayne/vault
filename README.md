# Vault - Pokemon TCG Portfolio Tracker

<div align="center">

![Vault Logo](https://img.shields.io/badge/Vault-Pokemon%20TCG-yellow?style=for-the-badge&logo=pokemon&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-green?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-orange?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)

### Track your Pokemon TCG collection's value with real-time pricing and financial analytics

[Features](#features) | [Quick Start](#quick-start) | [Screenshots](#screenshots) | [Documentation](#documentation)

</div>

---

## Why Vault?

Pokemon TCG collecting has become a serious investment for many. Whether you're tracking a handful of chase cards or managing a large collection, knowing your portfolio's real value matters. **Vault** gives you the financial tools to:

- See your collection's **total market value** update in real-time
- Track **daily price movements** across your holdings
- Calculate **profit & loss** with cost basis tracking
- Identify **concentration risk** in overweight positions
- Make **informed decisions** about buying, selling, or holding

---

## Screenshots

<div align="center">

### Dashboard Overview
![Dashboard](screenshots/dashboard.png)

### Portfolio Analytics
![Analytics](screenshots/analytics.png)

### Collection Management
![Collection](screenshots/collection.png)

</div>

---

## Features

### Portfolio Management
- Import collections from **Collectr CSV exports**
- Real-time price fetching from **Pokemon TCG API**
- Track **cards** and **sealed products** separately
- Store **price history** for trend analysis

### Modern Dashboard
- **Glassmorphism UI** with animated gradient backgrounds
- **Responsive design** - works on desktop, tablet, and mobile
- **Smooth animations** for polished user experience
- **Dark theme** optimized for extended viewing

### Financial Analytics
- **Total portfolio value** with daily change tracking
- **P&L calculation** - enter cost basis to see actual returns
- **Concentration analysis** - identify overweight positions
- **Top holdings** breakdown with percentage allocation
- **Best/worst performers** by P&L percentage

### Data Management
- **SQLite database** - lightweight, no server setup required
- **CSV import/export** for data portability
- **Editable cost basis** with auto-save functionality
- **CLI tools** for power users

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
git clone https://github.com/PryceWayne/vault.git
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

## Documentation

### Deployment

<details>
<summary><strong>Deploy to Railway (Recommended)</strong></summary>

1. Fork this repository
2. Go to [Railway.app](https://railway.app)
3. Click **"New Project"** → **"Deploy from GitHub"**
4. Select your forked repo
5. Railway auto-detects the Procfile and deploys

</details>

<details>
<summary><strong>Deploy to Render</strong></summary>

1. Fork this repository
2. Go to [Render.com](https://render.com)
3. Create new **"Web Service"**
4. Connect your GitHub repo
5. Set build command: `pip install -r requirements.txt`
6. Set start command: `gunicorn vault.web:app`

</details>

### CSV Format

The importer expects Collectr export format with these columns:

```
Portfolio Name, Category, Set, Product Name, Card Number,
Rarity, Variance, Grade, Card Condition, Average Cost Paid,
Quantity, Market Price, Price Override, Watchlist, Date Added, Notes
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/api/analysis` | GET | Portfolio analysis JSON |
| `/api/items` | GET | All items with prices |
| `/api/items/<id>/cost` | POST | Update item cost basis |

### Database Schema

```sql
items (
    id, name, set_name, card_number, rarity, variance,
    quantity, cost_basis, is_sealed, api_id, portfolio_name,
    grade, condition, notes, date_added, created_at, updated_at
)

prices (id, item_id, price, timestamp)

price_alerts (id, item_id, threshold_pct, direction, triggered_at)
```

---

## Contributing

Contributions are welcome! Feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [Pokemon TCG API](https://pokemontcg.io/) for market price data
- [Collectr](https://www.collectr.com/) for CSV export format compatibility
- [Tailwind CSS](https://tailwindcss.com/) for the styling framework
- [Chart.js](https://www.chartjs.org/) for data visualization

---

<div align="center">

**Built for Pokemon TCG collectors who take their portfolio seriously**

[Pryce Hedrick](https://github.com/PryceWayne)

</div>
