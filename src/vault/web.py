"""Web dashboard for Vault - Pokemon TCG Portfolio Tracker."""

import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
from . import database

app = Flask(__name__)

# ============================================================================
# ANALYSIS ENGINE
# ============================================================================

def analyze_portfolio():
    """Comprehensive portfolio analysis."""
    items = database.get_all_items()
    stats = database.get_summary_stats()

    if not items:
        return {"error": "No items in portfolio", "items": [], "total_value": 0}

    cards = [i for i in items if not i["is_sealed"]]
    sealed = [i for i in items if i["is_sealed"]]

    for item in items:
        item["total_value"] = (item["current_price"] or 0) * item["quantity"]
        if item["previous_price"] and item["current_price"]:
            item["change"] = item["current_price"] - item["previous_price"]
            item["change_pct"] = (item["change"] / item["previous_price"]) * 100
        else:
            item["change"] = 0
            item["change_pct"] = 0

        item["total_cost"] = (item["cost_basis"] or 0) * item["quantity"]
        if item["cost_basis"] and item["cost_basis"] > 0 and item["current_price"]:
            item["pnl"] = item["total_value"] - item["total_cost"]
            item["pnl_pct"] = ((item["current_price"] - item["cost_basis"]) / item["cost_basis"]) * 100
        else:
            item["pnl"] = None
            item["pnl_pct"] = None

    total_value = stats["total_value"] or 0
    cards_value = sum(i["total_value"] for i in cards)
    sealed_value = sum(i["total_value"] for i in sealed)

    sorted_by_value = sorted(items, key=lambda x: x["total_value"], reverse=True)
    top_5_value = sum(i["total_value"] for i in sorted_by_value[:5])
    top_5_pct = (top_5_value / total_value * 100) if total_value else 0

    with_changes = [i for i in items if i["change_pct"] != 0]
    gainers = sorted([i for i in with_changes if i["change_pct"] > 0], key=lambda x: x["change_pct"], reverse=True)[:5]
    losers = sorted([i for i in with_changes if i["change_pct"] < 0], key=lambda x: x["change_pct"])[:5]

    # Best performers by P&L
    with_pnl = [i for i in items if i["pnl_pct"] is not None]
    best_pnl = sorted(with_pnl, key=lambda x: x["pnl_pct"], reverse=True)[:5]
    worst_pnl = sorted(with_pnl, key=lambda x: x["pnl_pct"])[:5]

    sets = {}
    for item in items:
        set_name = item["set_name"] or "Unknown"
        if set_name not in sets:
            sets[set_name] = {"count": 0, "value": 0}
        sets[set_name]["count"] += item["quantity"]
        sets[set_name]["value"] += item["total_value"]

    return {
        "total_value": total_value,
        "total_cost": stats["total_cost"] or 0,
        "total_profit": stats["total_profit"],
        "item_count": stats["item_count"],
        "total_quantity": stats["total_quantity"],
        "daily_change": stats["daily_change"],
        "daily_change_pct": stats["daily_change_pct"],
        "composition": {
            "cards": {"count": len(cards), "value": cards_value, "pct": (cards_value/total_value*100) if total_value else 0},
            "sealed": {"count": len(sealed), "value": sealed_value, "pct": (sealed_value/total_value*100) if total_value else 0},
        },
        "concentration": {"top_5_value": top_5_value, "top_5_pct": top_5_pct, "top_holdings": sorted_by_value[:10]},
        "movers": {"gainers": gainers, "losers": losers},
        "performers": {"best": best_pnl, "worst": worst_pnl},
        "sets": sorted(sets.items(), key=lambda x: x[1]["value"], reverse=True)[:10],
        "items": items,
    }


def generate_recommendations(analysis):
    """AI recommendation engine."""
    recommendations = []
    total_value = analysis.get("total_value", 0)

    if total_value == 0:
        return [{"type": "info", "title": "Get Started", "message": "Import your collection to see insights.", "icon": "rocket"}]

    # Portfolio health
    health = 100
    issues = []

    if analysis["concentration"]["top_5_pct"] > 60:
        health -= 20
        issues.append("High concentration in top holdings")

    items_with_cost = len([i for i in analysis["items"] if i.get("cost_basis")])
    if items_with_cost < len(analysis["items"]) * 0.5:
        health -= 15
        issues.append("Missing cost basis on many items")

    sealed_pct = analysis["composition"]["sealed"]["pct"]
    if sealed_pct > 80:
        health -= 10
        issues.append("Portfolio heavily weighted to sealed")

    recommendations.append({
        "type": "success" if health >= 80 else "warning" if health >= 60 else "danger",
        "title": f"Portfolio Score: {health}/100",
        "message": "Excellent diversification!" if health >= 80 else f"Areas to improve: {', '.join(issues[:2])}",
        "icon": "trophy" if health >= 80 else "alert-triangle"
    })

    # Profit taking opportunities
    for item in analysis["performers"]["best"][:2]:
        if item["pnl_pct"] and item["pnl_pct"] > 50:
            recommendations.append({
                "type": "success",
                "title": f"Consider Profits: {item['name'][:25]}",
                "message": f"Up {item['pnl_pct']:.0f}% from cost basis. Lock in gains?",
                "icon": "trending-up"
            })

    # Loss review
    for item in analysis["performers"]["worst"][:1]:
        if item["pnl_pct"] and item["pnl_pct"] < -20:
            recommendations.append({
                "type": "danger",
                "title": f"Review: {item['name'][:25]}",
                "message": f"Down {abs(item['pnl_pct']):.0f}% from cost. Hold or cut losses?",
                "icon": "trending-down"
            })

    # Concentration warning
    if analysis["concentration"]["top_5_pct"] > 50:
        recommendations.append({
            "type": "warning",
            "title": "Concentration Risk",
            "message": f"Top 5 holdings = {analysis['concentration']['top_5_pct']:.0f}% of portfolio",
            "icon": "pie-chart"
        })

    return recommendations


DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vault | Pokemon TCG Portfolio</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                        display: ['Space Grotesk', 'sans-serif'],
                    },
                    animation: {
                        'gradient': 'gradient 8s linear infinite',
                        'float': 'float 6s ease-in-out infinite',
                        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                        'slide-up': 'slideUp 0.5s ease-out',
                        'fade-in': 'fadeIn 0.6s ease-out',
                    }
                }
            }
        }
    </script>
    <style>
        @keyframes gradient {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-20px); }
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .gradient-bg {
            background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #0f0c29);
            background-size: 400% 400%;
            animation: gradient 15s ease infinite;
        }
        .glass {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .glass-light {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        .dark .glass-light {
            background: rgba(30, 30, 40, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .glow {
            box-shadow: 0 0 40px rgba(139, 92, 246, 0.3);
        }
        .glow-green {
            box-shadow: 0 0 20px rgba(34, 197, 94, 0.4);
        }
        .glow-red {
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
        }
        .stat-card {
            transition: all 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-4px);
        }
        .pokemon-pattern {
            background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%239C92AC' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        }
        .table-container {
            scrollbar-width: thin;
            scrollbar-color: rgba(139, 92, 246, 0.5) transparent;
        }
        .table-container::-webkit-scrollbar {
            height: 8px;
        }
        .table-container::-webkit-scrollbar-track {
            background: transparent;
        }
        .table-container::-webkit-scrollbar-thumb {
            background: rgba(139, 92, 246, 0.5);
            border-radius: 4px;
        }
        input[type="number"]::-webkit-inner-spin-button,
        input[type="number"]::-webkit-outer-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        input[type="number"] {
            -moz-appearance: textfield;
        }
        .animate-in {
            animation: slideUp 0.5s ease-out forwards;
        }
        .delay-1 { animation-delay: 0.1s; }
        .delay-2 { animation-delay: 0.2s; }
        .delay-3 { animation-delay: 0.3s; }
        .delay-4 { animation-delay: 0.4s; }
    </style>
</head>
<body class="bg-gray-50 dark:bg-gray-900 min-h-screen font-sans transition-colors duration-300">
    <!-- Animated Background -->
    <div class="fixed inset-0 gradient-bg opacity-100 dark:opacity-100"></div>
    <div class="fixed inset-0 pokemon-pattern"></div>

    <!-- Floating Orbs -->
    <div class="fixed top-20 left-10 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-float"></div>
    <div class="fixed top-40 right-10 w-72 h-72 bg-yellow-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-float" style="animation-delay: 2s;"></div>
    <div class="fixed bottom-20 left-1/2 w-72 h-72 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-float" style="animation-delay: 4s;"></div>

    <div class="relative z-10">
        <!-- Header -->
        <header class="pt-8 pb-6 px-6">
            <div class="max-w-7xl mx-auto">
                <div class="glass rounded-3xl p-8 glow">
                    <div class="flex flex-col lg:flex-row items-center justify-between gap-6">
                        <div class="text-center lg:text-left">
                            <div class="flex items-center justify-center lg:justify-start gap-4 mb-2">
                                <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center shadow-lg">
                                    <svg class="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
                                        <circle cx="12" cy="12" r="3"/>
                                        <path d="M12 9c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3zm0 4c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1z"/>
                                    </svg>
                                </div>
                                <h1 class="text-4xl lg:text-5xl font-display font-bold text-white tracking-tight">
                                    Vault
                                </h1>
                            </div>
                            <p class="text-purple-200 text-lg">Pokemon TCG Portfolio Tracker</p>
                        </div>

                        <div class="text-center lg:text-right">
                            <div class="text-6xl lg:text-7xl font-display font-bold text-white mb-2">
                                ${{ "{:,.0f}".format(analysis.total_value) }}
                            </div>
                            <div class="flex items-center justify-center lg:justify-end gap-4 text-lg">
                                {% if analysis.daily_change != 0 %}
                                <span class="px-4 py-2 rounded-full {{ 'bg-green-500/20 text-green-300' if analysis.daily_change > 0 else 'bg-red-500/20 text-red-300' }} font-semibold">
                                    {{ "+" if analysis.daily_change > 0 else "" }}${{ "{:,.0f}".format(analysis.daily_change) }}
                                    ({{ "{:+.1f}".format(analysis.daily_change_pct) }}%)
                                </span>
                                {% endif %}
                                {% if analysis.total_profit is not none %}
                                <span class="px-4 py-2 rounded-full {{ 'bg-green-500/20 text-green-300' if analysis.total_profit >= 0 else 'bg-red-500/20 text-red-300' }} font-semibold">
                                    P&L: {{ "+" if analysis.total_profit >= 0 else "" }}${{ "{:,.0f}".format(analysis.total_profit) }}
                                </span>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="px-6 pb-12">
            <div class="max-w-7xl mx-auto">
                <!-- Stats Grid -->
                <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <div class="stat-card glass-light rounded-2xl p-6 animate-in opacity-0 delay-1">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
                                </svg>
                            </div>
                            <div>
                                <div class="text-3xl font-bold text-gray-800 dark:text-white">{{ analysis.item_count }}</div>
                                <div class="text-sm text-gray-500 dark:text-gray-400">Unique Items</div>
                            </div>
                        </div>
                    </div>

                    <div class="stat-card glass-light rounded-2xl p-6 animate-in opacity-0 delay-2">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center">
                                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>
                                </svg>
                            </div>
                            <div>
                                <div class="text-3xl font-bold text-gray-800 dark:text-white">{{ analysis.composition.cards.count }}</div>
                                <div class="text-sm text-gray-500 dark:text-gray-400">Cards</div>
                            </div>
                        </div>
                    </div>

                    <div class="stat-card glass-light rounded-2xl p-6 animate-in opacity-0 delay-3">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center">
                                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
                                </svg>
                            </div>
                            <div>
                                <div class="text-3xl font-bold text-gray-800 dark:text-white">{{ analysis.composition.sealed.count }}</div>
                                <div class="text-sm text-gray-500 dark:text-gray-400">Sealed</div>
                            </div>
                        </div>
                    </div>

                    <div class="stat-card glass-light rounded-2xl p-6 animate-in opacity-0 delay-4">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
                                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                </svg>
                            </div>
                            <div>
                                <div class="text-3xl font-bold text-gray-800 dark:text-white">${{ "{:,.0f}".format(analysis.total_cost) }}</div>
                                <div class="text-sm text-gray-500 dark:text-gray-400">Invested</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Three Column Layout -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                    <!-- AI Insights -->
                    <div class="glass-light rounded-2xl p-6 animate-in opacity-0" style="animation-delay: 0.5s;">
                        <h2 class="text-xl font-bold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1v1a2 2 0 01-2 2H5a2 2 0 01-2-2v-1H2a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
                                </svg>
                            </span>
                            AI Insights
                        </h2>
                        <div class="space-y-3">
                            {% for rec in recommendations %}
                            <div class="p-4 rounded-xl {{ 'bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500' if rec.type == 'success' else 'bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500' if rec.type == 'warning' else 'bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500' if rec.type == 'danger' else 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500' }}">
                                <div class="font-semibold text-gray-800 dark:text-white text-sm">{{ rec.title }}</div>
                                <div class="text-gray-600 dark:text-gray-300 text-sm mt-1">{{ rec.message }}</div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- Top Holdings -->
                    <div class="glass-light rounded-2xl p-6 animate-in opacity-0" style="animation-delay: 0.6s;">
                        <h2 class="text-xl font-bold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-yellow-500 to-orange-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                                </svg>
                            </span>
                            Top Holdings
                        </h2>
                        <div class="space-y-3">
                            {% for item in analysis.concentration.top_holdings[:6] %}
                            <div class="flex items-center justify-between p-3 rounded-xl bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                                <div class="flex-1 min-w-0">
                                    <div class="font-medium text-gray-800 dark:text-white truncate text-sm">{{ item.name[:28] }}</div>
                                    <div class="text-xs text-gray-500">{{ item.set_name[:20] if item.set_name else 'Unknown' }}</div>
                                </div>
                                <div class="text-right ml-3">
                                    <div class="font-bold text-gray-800 dark:text-white">${{ "{:,.0f}".format(item.total_value) }}</div>
                                    <div class="text-xs text-gray-500">{{ "{:.1f}".format(item.total_value / analysis.total_value * 100 if analysis.total_value else 0) }}%</div>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- Portfolio Breakdown -->
                    <div class="glass-light rounded-2xl p-6 animate-in opacity-0" style="animation-delay: 0.7s;">
                        <h2 class="text-xl font-bold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/>
                                    <path d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/>
                                </svg>
                            </span>
                            Breakdown
                        </h2>
                        <div class="mb-6">
                            <canvas id="compositionChart" height="180"></canvas>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div class="text-center p-3 rounded-xl bg-blue-50 dark:bg-blue-900/20">
                                <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">${{ "{:,.0f}".format(analysis.composition.cards.value) }}</div>
                                <div class="text-xs text-gray-500">Cards ({{ "{:.0f}".format(analysis.composition.cards.pct) }}%)</div>
                            </div>
                            <div class="text-center p-3 rounded-xl bg-orange-50 dark:bg-orange-900/20">
                                <div class="text-2xl font-bold text-orange-600 dark:text-orange-400">${{ "{:,.0f}".format(analysis.composition.sealed.value) }}</div>
                                <div class="text-xs text-gray-500">Sealed ({{ "{:.0f}".format(analysis.composition.sealed.pct) }}%)</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Collection Table -->
                <div class="glass-light rounded-2xl p-6 animate-in opacity-0" style="animation-delay: 0.8s;">
                    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
                        <h2 class="text-xl font-bold text-gray-800 dark:text-white flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
                                </svg>
                            </span>
                            Full Collection
                        </h2>
                        <div class="flex items-center gap-3">
                            <span id="saveStatus" class="text-sm text-green-600 dark:text-green-400 hidden transition-opacity">
                                <svg class="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                                Saved
                            </span>
                            <div class="relative">
                                <input type="text" id="searchInput" placeholder="Search collection..."
                                       class="w-64 pl-10 pr-4 py-2 bg-gray-100 dark:bg-gray-800 border-0 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 dark:text-white">
                                <svg class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                                </svg>
                            </div>
                        </div>
                    </div>

                    <div class="table-container overflow-x-auto">
                        <table class="w-full" id="collectionTable">
                            <thead>
                                <tr class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    <th class="pb-4 cursor-pointer hover:text-purple-600" onclick="sortTable(0)">Name</th>
                                    <th class="pb-4 cursor-pointer hover:text-purple-600 hidden md:table-cell" onclick="sortTable(1)">Set</th>
                                    <th class="pb-4 text-center cursor-pointer hover:text-purple-600" onclick="sortTable(2)">Qty</th>
                                    <th class="pb-4 text-right cursor-pointer hover:text-purple-600" onclick="sortTable(3)">Price</th>
                                    <th class="pb-4 text-right cursor-pointer hover:text-purple-600" onclick="sortTable(4)">Value</th>
                                    <th class="pb-4 text-right" title="Your purchase price per unit">Cost</th>
                                    <th class="pb-4 text-right cursor-pointer hover:text-purple-600" onclick="sortTable(6)">Return</th>
                                    <th class="pb-4 text-center hidden sm:table-cell">Type</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
                                {% for item in analysis.items|sort(attribute='total_value', reverse=true) %}
                                <tr class="group hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors" data-item-id="{{ item.id }}">
                                    <td class="py-4 pr-4">
                                        <div class="font-medium text-gray-800 dark:text-white">{{ item.name[:35] }}</div>
                                        <div class="text-xs text-gray-400 md:hidden">{{ item.set_name[:20] if item.set_name else '-' }}</div>
                                    </td>
                                    <td class="py-4 text-gray-600 dark:text-gray-300 text-sm hidden md:table-cell">{{ item.set_name[:22] if item.set_name else '-' }}</td>
                                    <td class="py-4 text-center text-gray-800 dark:text-white">{{ item.quantity }}</td>
                                    <td class="py-4 text-right text-gray-800 dark:text-white">${{ "{:,.2f}".format(item.current_price) if item.current_price else '-' }}</td>
                                    <td class="py-4 text-right font-semibold text-gray-800 dark:text-white">${{ "{:,.0f}".format(item.total_value) }}</td>
                                    <td class="py-4 text-right">
                                        <div class="inline-flex items-center">
                                            <span class="text-gray-400 mr-1 text-sm">$</span>
                                            <input type="number" step="0.01" min="0"
                                                   class="cost-input w-16 px-2 py-1 text-right text-sm bg-gray-100 dark:bg-gray-800 border-0 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 dark:text-white"
                                                   data-item-id="{{ item.id }}"
                                                   data-current-price="{{ item.current_price or 0 }}"
                                                   data-quantity="{{ item.quantity }}"
                                                   value="{{ '{:.2f}'.format(item.cost_basis) if item.cost_basis else '' }}"
                                                   placeholder="0.00">
                                        </div>
                                    </td>
                                    <td class="py-4 text-right pnl-cell" data-item-id="{{ item.id }}">
                                        {% if item.pnl_pct is not none %}
                                        <span class="inline-flex items-center px-2 py-1 rounded-lg text-sm font-semibold {{ 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' if item.pnl_pct >= 0 else 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' }}">
                                            {{ "{:+.0f}".format(item.pnl_pct) }}%
                                        </span>
                                        {% else %}
                                        <span class="text-gray-400 text-sm">-</span>
                                        {% endif %}
                                    </td>
                                    <td class="py-4 text-center hidden sm:table-cell">
                                        {% if item.is_sealed %}
                                        <span class="px-2 py-1 rounded-lg text-xs font-semibold bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400">Sealed</span>
                                        {% else %}
                                        <span class="px-2 py-1 rounded-lg text-xs font-semibold bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">Card</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Footer -->
                <footer class="mt-8 text-center">
                    <div class="glass rounded-2xl p-6 inline-block">
                        <p class="text-purple-200 text-sm">
                            Built with <span class="text-red-400">&hearts;</span> for Pokemon TCG collectors
                        </p>
                        <p class="text-purple-300/50 text-xs mt-2">
                            Last updated: {{ now.strftime('%B %d, %Y at %I:%M %p') }}
                        </p>
                    </div>
                </footer>
            </div>
        </main>
    </div>

    <script>
        // Trigger animations on load
        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('.animate-in').forEach(el => {
                el.style.opacity = '1';
            });
        });

        // Composition Chart
        const compCtx = document.getElementById('compositionChart').getContext('2d');
        new Chart(compCtx, {
            type: 'doughnut',
            data: {
                labels: ['Cards', 'Sealed'],
                datasets: [{
                    data: [{{ analysis.composition.cards.value }}, {{ analysis.composition.sealed.value }}],
                    backgroundColor: ['#3B82F6', '#F59E0B'],
                    borderWidth: 0,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                cutout: '70%',
                plugins: {
                    legend: { display: false }
                }
            }
        });

        // Search functionality
        document.getElementById('searchInput').addEventListener('keyup', function() {
            const filter = this.value.toLowerCase();
            document.querySelectorAll('#collectionTable tbody tr').forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(filter) ? '' : 'none';
            });
        });

        // Sort functionality
        let sortDirection = {};
        function sortTable(column) {
            const tbody = document.querySelector('#collectionTable tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            sortDirection[column] = !sortDirection[column];
            const dir = sortDirection[column] ? 1 : -1;
            rows.sort((a, b) => {
                let aVal = a.cells[column]?.textContent.trim() || '';
                let bVal = b.cells[column]?.textContent.trim() || '';
                if (column >= 2 && column <= 6) {
                    aVal = parseFloat(aVal.replace(/[$,%+]/g, '')) || 0;
                    bVal = parseFloat(bVal.replace(/[$,%+]/g, '')) || 0;
                    return (aVal - bVal) * dir;
                }
                return aVal.localeCompare(bVal) * dir;
            });
            rows.forEach(row => tbody.appendChild(row));
        }

        // Cost basis editing
        document.querySelectorAll('.cost-input').forEach(input => {
            input.addEventListener('change', function() {
                const itemId = this.dataset.itemId;
                const cost = parseFloat(this.value) || 0;
                const price = parseFloat(this.dataset.currentPrice) || 0;
                const qty = parseInt(this.dataset.quantity) || 1;

                // Update return display
                const cell = document.querySelector(`.pnl-cell[data-item-id="${itemId}"]`);
                if (cost > 0 && price > 0) {
                    const pnl = ((price - cost) / cost) * 100;
                    const cls = pnl >= 0
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                        : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400';
                    cell.innerHTML = `<span class="inline-flex items-center px-2 py-1 rounded-lg text-sm font-semibold ${cls}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)}%</span>`;
                } else {
                    cell.innerHTML = '<span class="text-gray-400 text-sm">-</span>';
                }

                // Save to server
                fetch(`/api/items/${itemId}/cost`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cost_basis: cost })
                }).then(r => r.json()).then(data => {
                    if (data.success) {
                        const status = document.getElementById('saveStatus');
                        status.classList.remove('hidden');
                        setTimeout(() => status.classList.add('hidden'), 2000);
                    }
                });
            });
        });
    </script>
</body>
</html>
'''


@app.route('/')
def dashboard():
    database.init_db()
    analysis = analyze_portfolio()
    recommendations = generate_recommendations(analysis)

    class Obj:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, Obj(v) if isinstance(v, dict) else v)

    obj = Obj(analysis)
    obj.items = analysis["items"]
    obj.sets = analysis["sets"]
    obj.concentration = Obj(analysis["concentration"])
    obj.concentration.top_holdings = analysis["concentration"]["top_holdings"]
    obj.movers = Obj(analysis["movers"])
    obj.movers.gainers = analysis["movers"]["gainers"]
    obj.movers.losers = analysis["movers"]["losers"]
    obj.performers = Obj(analysis["performers"])
    obj.performers.best = analysis["performers"]["best"]
    obj.performers.worst = analysis["performers"]["worst"]

    return render_template_string(DASHBOARD_HTML, analysis=obj, recommendations=recommendations, now=datetime.now())


@app.route('/api/analysis')
def api_analysis():
    database.init_db()
    return jsonify({"analysis": analyze_portfolio(), "recommendations": generate_recommendations(analyze_portfolio())})


@app.route('/api/items')
def api_items():
    database.init_db()
    return jsonify(database.get_all_items())


@app.route('/api/items/<int:item_id>/cost', methods=['POST'])
def update_cost_basis(item_id):
    database.init_db()
    data = request.get_json()
    success = database.update_item_cost_basis(item_id, data.get('cost_basis', 0))
    return jsonify({"success": success})


def run_server(host='127.0.0.1', port=5000, debug=False):
    app.run(host=host, port=port, debug=debug)
