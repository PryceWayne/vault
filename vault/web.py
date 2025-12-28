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
        return {
            "error": "No items in portfolio",
            "items": [],
            "total_value": 0,
            "total_cost": 0,
            "total_profit": None,
            "item_count": 0,
            "total_quantity": 0,
            "daily_change": 0,
            "daily_change_pct": 0,
            "composition": {
                "cards": {"count": 0, "value": 0, "pct": 0},
                "sealed": {"count": 0, "value": 0, "pct": 0},
            },
            "concentration": {"top_5_value": 0, "top_5_pct": 0, "top_holdings": []},
            "movers": {"gainers": [], "losers": []},
            "performers": {"best": [], "worst": []},
            "sets": [],
        }

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
    """AI recommendation engine with enhanced insights."""
    recommendations = []
    total_value = analysis.get("total_value", 0)

    if total_value == 0:
        return [{"type": "info", "title": "Get Started", "message": "Import your collection to see insights.", "icon": "rocket"}]

    # Portfolio health score
    health = 100
    issues = []

    if analysis["concentration"]["top_5_pct"] > 60:
        health -= 20
        issues.append("High concentration in top holdings")

    items_with_cost = len([i for i in analysis["items"] if i.get("cost_basis")])
    cost_coverage = items_with_cost / len(analysis["items"]) if analysis["items"] else 0
    if cost_coverage < 0.5:
        health -= 15
        issues.append("Missing cost basis on many items")

    sealed_pct = analysis["composition"]["sealed"]["pct"]
    if sealed_pct > 80:
        health -= 10
        issues.append("Portfolio heavily weighted to sealed")

    # Calculate ROI if we have cost data
    if analysis["total_cost"] and analysis["total_cost"] > 0:
        roi = ((analysis["total_value"] - analysis["total_cost"]) / analysis["total_cost"]) * 100
        if roi > 20:
            health = min(100, health + 10)
        elif roi < -10:
            health -= 10

    recommendations.append({
        "type": "success" if health >= 80 else "warning" if health >= 60 else "danger",
        "title": f"Portfolio Health: {health}/100",
        "message": "Excellent diversification and tracking!" if health >= 80 else f"Areas to improve: {', '.join(issues[:2])}",
        "icon": "trophy" if health >= 80 else "alert-triangle"
    })

    # Market momentum
    gainers_count = len(analysis["movers"]["gainers"])
    losers_count = len(analysis["movers"]["losers"])
    if gainers_count > losers_count:
        recommendations.append({
            "type": "success",
            "title": "Positive Momentum",
            "message": f"{gainers_count} items rising vs {losers_count} falling. Market favoring your holdings.",
            "icon": "trending-up"
        })
    elif losers_count > gainers_count and losers_count > 3:
        recommendations.append({
            "type": "warning",
            "title": "Market Pressure",
            "message": f"{losers_count} items declining. Consider reviewing weak positions.",
            "icon": "trending-down"
        })

    # Profit taking opportunities
    for item in analysis["performers"]["best"][:2]:
        if item["pnl_pct"] and item["pnl_pct"] > 50:
            recommendations.append({
                "type": "success",
                "title": f"Take Profits? {item['name'][:22]}...",
                "message": f"Up {item['pnl_pct']:.0f}% from cost. Consider locking in gains.",
                "icon": "dollar-sign"
            })

    # Loss review
    for item in analysis["performers"]["worst"][:1]:
        if item["pnl_pct"] and item["pnl_pct"] < -25:
            recommendations.append({
                "type": "danger",
                "title": f"Review: {item['name'][:22]}...",
                "message": f"Down {abs(item['pnl_pct']):.0f}% from cost. Hold conviction or cut losses?",
                "icon": "alert-circle"
            })

    # Concentration warning
    if analysis["concentration"]["top_5_pct"] > 50:
        recommendations.append({
            "type": "warning",
            "title": "Concentration Risk",
            "message": f"Top 5 holdings = {analysis['concentration']['top_5_pct']:.0f}% of portfolio. Consider diversifying.",
            "icon": "pie-chart"
        })

    # Cost tracking reminder
    if cost_coverage < 0.7:
        recommendations.append({
            "type": "info",
            "title": "Track Your Costs",
            "message": f"Only {cost_coverage*100:.0f}% of items have cost basis. Add costs for accurate P&L.",
            "icon": "edit"
        })

    return recommendations[:6]  # Limit to 6 recommendations


DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en" class="dark">
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
                    colors: {
                        dark: {
                            900: '#0a0a0f',
                            800: '#12121a',
                            700: '#1a1a24',
                            600: '#24242f',
                        }
                    },
                    animation: {
                        'gradient': 'gradient 8s linear infinite',
                        'float': 'float 6s ease-in-out infinite',
                        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
                        'slide-up': 'slideUp 0.5s ease-out forwards',
                        'fade-in': 'fadeIn 0.6s ease-out forwards',
                        'number-tick': 'numberTick 0.3s ease-out',
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
        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); }
            50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.6); }
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
            background: linear-gradient(-45deg, #0a0a0f, #1a1a2e, #16213e, #0f0f1a);
            background-size: 400% 400%;
            animation: gradient 15s ease infinite;
        }
        .glass {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.06);
            transition: all 0.3s ease;
        }
        .glass-card:hover {
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(139, 92, 246, 0.3);
            transform: translateY(-2px);
        }
        .glow-purple {
            box-shadow: 0 0 40px rgba(139, 92, 246, 0.2);
        }
        .glow-green {
            box-shadow: 0 0 20px rgba(34, 197, 94, 0.3);
        }
        .glow-red {
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
        }
        .stat-value {
            background: linear-gradient(135deg, #fff 0%, #e0e0e0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .gradient-text {
            background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 50%, #7c3aed 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .pokemon-pattern {
            background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%239C92AC' fill-opacity='0.02'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        }
        .table-container::-webkit-scrollbar {
            height: 6px;
            width: 6px;
        }
        .table-container::-webkit-scrollbar-track {
            background: transparent;
        }
        .table-container::-webkit-scrollbar-thumb {
            background: rgba(139, 92, 246, 0.3);
            border-radius: 3px;
        }
        .table-container::-webkit-scrollbar-thumb:hover {
            background: rgba(139, 92, 246, 0.5);
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
            opacity: 0;
            animation: slideUp 0.5s ease-out forwards;
        }
        .delay-1 { animation-delay: 0.1s; }
        .delay-2 { animation-delay: 0.2s; }
        .delay-3 { animation-delay: 0.3s; }
        .delay-4 { animation-delay: 0.4s; }
        .delay-5 { animation-delay: 0.5s; }
        .tab-active {
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
            border-color: rgba(139, 92, 246, 0.5);
        }
    </style>
</head>
<body class="bg-dark-900 min-h-screen font-sans text-white">
    <!-- Animated Background -->
    <div class="fixed inset-0 gradient-bg"></div>
    <div class="fixed inset-0 pokemon-pattern"></div>

    <!-- Floating Orbs -->
    <div class="fixed top-20 left-10 w-96 h-96 bg-purple-600 rounded-full mix-blend-screen filter blur-[128px] opacity-20 animate-float"></div>
    <div class="fixed bottom-20 right-10 w-96 h-96 bg-yellow-500 rounded-full mix-blend-screen filter blur-[128px] opacity-15 animate-float" style="animation-delay: 3s;"></div>
    <div class="fixed top-1/2 left-1/2 w-72 h-72 bg-blue-500 rounded-full mix-blend-screen filter blur-[100px] opacity-10 animate-float" style="animation-delay: 5s;"></div>

    <div class="relative z-10">
        <!-- Header -->
        <header class="pt-6 pb-4 px-4 md:px-6">
            <div class="max-w-7xl mx-auto">
                <div class="glass rounded-3xl p-6 md:p-8 glow-purple">
                    <div class="flex flex-col lg:flex-row items-center justify-between gap-6">
                        <!-- Logo & Title -->
                        <div class="text-center lg:text-left">
                            <div class="flex items-center justify-center lg:justify-start gap-4 mb-2">
                                <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-yellow-400 via-orange-500 to-red-500 flex items-center justify-center shadow-lg shadow-orange-500/30">
                                    <svg class="w-8 h-8 text-white" viewBox="0 0 24 24" fill="currentColor">
                                        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/>
                                        <circle cx="12" cy="12" r="3" fill="currentColor"/>
                                        <line x1="2" y1="12" x2="9" y2="12" stroke="currentColor" stroke-width="2"/>
                                        <line x1="15" y1="12" x2="22" y2="12" stroke="currentColor" stroke-width="2"/>
                                    </svg>
                                </div>
                                <div>
                                    <h1 class="text-3xl md:text-4xl font-display font-bold text-white tracking-tight">
                                        Vault
                                    </h1>
                                    <p class="text-purple-300/80 text-sm">Pokemon TCG Portfolio</p>
                                </div>
                            </div>
                        </div>

                        <!-- Portfolio Value -->
                        <div class="text-center lg:text-right">
                            <div class="text-5xl md:text-6xl lg:text-7xl font-display font-bold stat-value mb-2">
                                ${{ "{:,.0f}".format(analysis.total_value) }}
                            </div>
                            <div class="flex flex-wrap items-center justify-center lg:justify-end gap-3">
                                {% if analysis.daily_change != 0 %}
                                <span class="px-4 py-1.5 rounded-full text-sm font-semibold {{ 'bg-green-500/20 text-green-400 glow-green' if analysis.daily_change > 0 else 'bg-red-500/20 text-red-400 glow-red' }}">
                                    <span class="inline-flex items-center gap-1">
                                        {% if analysis.daily_change > 0 %}
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/></svg>
                                        {% else %}
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/></svg>
                                        {% endif %}
                                        {{ "{:+.1f}".format(analysis.daily_change_pct) }}% today
                                    </span>
                                </span>
                                {% endif %}
                                {% if analysis.total_profit is not none %}
                                <span class="px-4 py-1.5 rounded-full text-sm font-semibold {{ 'bg-green-500/20 text-green-400' if analysis.total_profit >= 0 else 'bg-red-500/20 text-red-400' }}">
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
        <main class="px-4 md:px-6 pb-12">
            <div class="max-w-7xl mx-auto">
                <!-- Quick Stats -->
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-6">
                    <div class="glass-card rounded-2xl p-4 md:p-5 animate-in delay-1">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                                <svg class="w-5 h-5 md:w-6 md:h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
                                </svg>
                            </div>
                            <div class="min-w-0">
                                <div class="text-2xl md:text-3xl font-bold text-white">{{ analysis.item_count }}</div>
                                <div class="text-xs md:text-sm text-gray-400 truncate">Unique Items</div>
                            </div>
                        </div>
                    </div>

                    <div class="glass-card rounded-2xl p-4 md:p-5 animate-in delay-2">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
                                <svg class="w-5 h-5 md:w-6 md:h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>
                                </svg>
                            </div>
                            <div class="min-w-0">
                                <div class="text-2xl md:text-3xl font-bold text-white">{{ analysis.composition.cards.count }}</div>
                                <div class="text-xs md:text-sm text-gray-400 truncate">Cards</div>
                            </div>
                        </div>
                    </div>

                    <div class="glass-card rounded-2xl p-4 md:p-5 animate-in delay-3">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center flex-shrink-0">
                                <svg class="w-5 h-5 md:w-6 md:h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
                                </svg>
                            </div>
                            <div class="min-w-0">
                                <div class="text-2xl md:text-3xl font-bold text-white">{{ analysis.composition.sealed.count }}</div>
                                <div class="text-xs md:text-sm text-gray-400 truncate">Sealed</div>
                            </div>
                        </div>
                    </div>

                    <div class="glass-card rounded-2xl p-4 md:p-5 animate-in delay-4">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center flex-shrink-0">
                                <svg class="w-5 h-5 md:w-6 md:h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                </svg>
                            </div>
                            <div class="min-w-0">
                                <div class="text-2xl md:text-3xl font-bold text-white">${{ "{:,.0f}".format(analysis.total_cost) }}</div>
                                <div class="text-xs md:text-sm text-gray-400 truncate">Invested</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Main Grid -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6 mb-6">
                    <!-- AI Insights -->
                    <div class="glass-card rounded-2xl p-5 md:p-6 animate-in delay-5">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1v1a2 2 0 01-2 2H5a2 2 0 01-2-2v-1H2a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
                                </svg>
                            </span>
                            <span class="gradient-text">AI Insights</span>
                        </h2>
                        <div class="space-y-3 max-h-80 overflow-y-auto pr-2">
                            {% for rec in recommendations %}
                            <div class="p-3 rounded-xl {{ 'bg-green-500/10 border border-green-500/20' if rec.type == 'success' else 'bg-yellow-500/10 border border-yellow-500/20' if rec.type == 'warning' else 'bg-red-500/10 border border-red-500/20' if rec.type == 'danger' else 'bg-blue-500/10 border border-blue-500/20' }}">
                                <div class="font-semibold text-sm {{ 'text-green-400' if rec.type == 'success' else 'text-yellow-400' if rec.type == 'warning' else 'text-red-400' if rec.type == 'danger' else 'text-blue-400' }}">{{ rec.title }}</div>
                                <div class="text-gray-400 text-xs mt-1 leading-relaxed">{{ rec.message }}</div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- Top Holdings -->
                    <div class="glass-card rounded-2xl p-5 md:p-6 animate-in" style="animation-delay: 0.6s;">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-yellow-500 to-orange-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                                </svg>
                            </span>
                            Top Holdings
                        </h2>
                        <div class="space-y-2 max-h-80 overflow-y-auto pr-2">
                            {% for item in analysis.concentration.top_holdings[:8] %}
                            <div class="flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors group">
                                <div class="flex-1 min-w-0 mr-3">
                                    <div class="font-medium text-white text-sm truncate group-hover:text-purple-300 transition-colors">{{ item.name[:30] }}</div>
                                    <div class="text-xs text-gray-500 truncate">{{ item.set_name[:25] if item.set_name else 'Unknown Set' }}</div>
                                </div>
                                <div class="text-right flex-shrink-0">
                                    <div class="font-bold text-white text-sm">${{ "{:,.0f}".format(item.total_value) }}</div>
                                    <div class="text-xs text-gray-500">{{ "{:.1f}".format(item.total_value / analysis.total_value * 100 if analysis.total_value else 0) }}%</div>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- Portfolio Breakdown -->
                    <div class="glass-card rounded-2xl p-5 md:p-6 animate-in" style="animation-delay: 0.7s;">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/>
                                    <path d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/>
                                </svg>
                            </span>
                            Breakdown
                        </h2>
                        <div class="mb-6">
                            <canvas id="compositionChart" height="160"></canvas>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div class="text-center p-3 rounded-xl bg-blue-500/10 border border-blue-500/20">
                                <div class="text-xl font-bold text-blue-400">${{ "{:,.0f}".format(analysis.composition.cards.value) }}</div>
                                <div class="text-xs text-gray-400 mt-1">Cards ({{ "{:.0f}".format(analysis.composition.cards.pct) }}%)</div>
                            </div>
                            <div class="text-center p-3 rounded-xl bg-orange-500/10 border border-orange-500/20">
                                <div class="text-xl font-bold text-orange-400">${{ "{:,.0f}".format(analysis.composition.sealed.value) }}</div>
                                <div class="text-xs text-gray-400 mt-1">Sealed ({{ "{:.0f}".format(analysis.composition.sealed.pct) }}%)</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Movers Section -->
                {% if analysis.movers.gainers or analysis.movers.losers %}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 mb-6">
                    <!-- Gainers -->
                    <div class="glass-card rounded-2xl p-5 md:p-6 animate-in" style="animation-delay: 0.8s;">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                                </svg>
                            </span>
                            <span class="text-green-400">Top Gainers</span>
                        </h2>
                        <div class="space-y-2">
                            {% for item in analysis.movers.gainers[:5] %}
                            <div class="flex items-center justify-between p-3 rounded-xl bg-green-500/5 border border-green-500/10">
                                <div class="flex-1 min-w-0 mr-3">
                                    <div class="font-medium text-white text-sm truncate">{{ item.name[:28] }}</div>
                                    <div class="text-xs text-gray-500">${{ "{:.2f}".format(item.current_price) if item.current_price else '-' }}</div>
                                </div>
                                <span class="px-3 py-1 rounded-full text-sm font-bold bg-green-500/20 text-green-400">
                                    +{{ "{:.1f}".format(item.change_pct) }}%
                                </span>
                            </div>
                            {% else %}
                            <div class="text-center text-gray-500 py-4 text-sm">No gainers today</div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- Losers -->
                    <div class="glass-card rounded-2xl p-5 md:p-6 animate-in" style="animation-delay: 0.9s;">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-rose-500 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/>
                                </svg>
                            </span>
                            <span class="text-red-400">Top Losers</span>
                        </h2>
                        <div class="space-y-2">
                            {% for item in analysis.movers.losers[:5] %}
                            <div class="flex items-center justify-between p-3 rounded-xl bg-red-500/5 border border-red-500/10">
                                <div class="flex-1 min-w-0 mr-3">
                                    <div class="font-medium text-white text-sm truncate">{{ item.name[:28] }}</div>
                                    <div class="text-xs text-gray-500">${{ "{:.2f}".format(item.current_price) if item.current_price else '-' }}</div>
                                </div>
                                <span class="px-3 py-1 rounded-full text-sm font-bold bg-red-500/20 text-red-400">
                                    {{ "{:.1f}".format(item.change_pct) }}%
                                </span>
                            </div>
                            {% else %}
                            <div class="text-center text-gray-500 py-4 text-sm">No losers today</div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                {% endif %}

                <!-- Collection Table -->
                <div class="glass-card rounded-2xl p-5 md:p-6 animate-in" style="animation-delay: 1s;">
                    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
                        <h2 class="text-lg font-bold text-white flex items-center gap-2">
                            <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
                                </svg>
                            </span>
                            Full Collection
                            <span class="text-sm font-normal text-gray-500">({{ analysis.items|length }} items)</span>
                        </h2>
                        <div class="flex items-center gap-3 w-full sm:w-auto">
                            <span id="saveStatus" class="text-sm text-green-400 hidden transition-opacity">
                                <svg class="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                                Saved
                            </span>
                            <div class="relative flex-1 sm:flex-initial">
                                <input type="text" id="searchInput" placeholder="Search..."
                                       class="w-full sm:w-56 pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-white placeholder-gray-500">
                                <svg class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                                </svg>
                            </div>
                        </div>
                    </div>

                    <div class="table-container overflow-x-auto -mx-5 md:-mx-6 px-5 md:px-6">
                        <table class="w-full min-w-[700px]" id="collectionTable">
                            <thead>
                                <tr class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-white/5">
                                    <th class="pb-4 cursor-pointer hover:text-purple-400 transition-colors" onclick="sortTable(0)">Name</th>
                                    <th class="pb-4 cursor-pointer hover:text-purple-400 transition-colors hidden md:table-cell" onclick="sortTable(1)">Set</th>
                                    <th class="pb-4 text-center cursor-pointer hover:text-purple-400 transition-colors" onclick="sortTable(2)">Qty</th>
                                    <th class="pb-4 text-right cursor-pointer hover:text-purple-400 transition-colors" onclick="sortTable(3)">Price</th>
                                    <th class="pb-4 text-right cursor-pointer hover:text-purple-400 transition-colors" onclick="sortTable(4)">Value</th>
                                    <th class="pb-4 text-right" title="Your purchase price per unit">Cost</th>
                                    <th class="pb-4 text-right cursor-pointer hover:text-purple-400 transition-colors" onclick="sortTable(6)">P&L</th>
                                    <th class="pb-4 text-center hidden sm:table-cell">Type</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-white/5">
                                {% for item in analysis.items|sort(attribute='total_value', reverse=true) %}
                                <tr class="group hover:bg-white/5 transition-colors" data-item-id="{{ item.id }}">
                                    <td class="py-4 pr-4">
                                        <div class="font-medium text-white text-sm group-hover:text-purple-300 transition-colors">{{ item.name[:32] }}</div>
                                        <div class="text-xs text-gray-500 md:hidden">{{ item.set_name[:20] if item.set_name else '-' }}</div>
                                    </td>
                                    <td class="py-4 text-gray-400 text-sm hidden md:table-cell">{{ item.set_name[:20] if item.set_name else '-' }}</td>
                                    <td class="py-4 text-center text-white text-sm">{{ item.quantity }}</td>
                                    <td class="py-4 text-right text-gray-300 text-sm">${{ "{:,.2f}".format(item.current_price) if item.current_price else '-' }}</td>
                                    <td class="py-4 text-right font-semibold text-white text-sm">${{ "{:,.0f}".format(item.total_value) }}</td>
                                    <td class="py-4 text-right">
                                        <div class="inline-flex items-center">
                                            <span class="text-gray-500 mr-1 text-sm">$</span>
                                            <input type="number" step="0.01" min="0"
                                                   class="cost-input w-16 px-2 py-1 text-right text-sm bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-white"
                                                   data-item-id="{{ item.id }}"
                                                   data-current-price="{{ item.current_price or 0 }}"
                                                   data-quantity="{{ item.quantity }}"
                                                   value="{{ '{:.2f}'.format(item.cost_basis) if item.cost_basis else '' }}"
                                                   placeholder="0.00">
                                        </div>
                                    </td>
                                    <td class="py-4 text-right pnl-cell" data-item-id="{{ item.id }}">
                                        {% if item.pnl_pct is not none %}
                                        <span class="inline-flex items-center px-2 py-1 rounded-lg text-xs font-semibold {{ 'bg-green-500/20 text-green-400' if item.pnl_pct >= 0 else 'bg-red-500/20 text-red-400' }}">
                                            {{ "{:+.0f}".format(item.pnl_pct) }}%
                                        </span>
                                        {% else %}
                                        <span class="text-gray-600 text-sm">—</span>
                                        {% endif %}
                                    </td>
                                    <td class="py-4 text-center hidden sm:table-cell">
                                        {% if item.is_sealed %}
                                        <span class="px-2 py-1 rounded-lg text-xs font-medium bg-orange-500/20 text-orange-400">Sealed</span>
                                        {% else %}
                                        <span class="px-2 py-1 rounded-lg text-xs font-medium bg-blue-500/20 text-blue-400">Card</span>
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
                    <div class="glass rounded-2xl p-5 inline-block">
                        <p class="text-gray-400 text-sm">
                            Built with <span class="text-red-400">♥</span> for Pokemon TCG collectors
                        </p>
                        <p class="text-gray-600 text-xs mt-2">
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
        const compCtx = document.getElementById('compositionChart');
        if (compCtx) {
            new Chart(compCtx.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: ['Cards', 'Sealed'],
                    datasets: [{
                        data: [{{ analysis.composition.cards.value }}, {{ analysis.composition.sealed.value }}],
                        backgroundColor: ['#3B82F6', '#F59E0B'],
                        borderWidth: 0,
                        borderRadius: 4,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    cutout: '75%',
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

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
                    aVal = parseFloat(aVal.replace(/[$,%+—]/g, '')) || 0;
                    bVal = parseFloat(bVal.replace(/[$,%+—]/g, '')) || 0;
                    return (aVal - bVal) * dir;
                }
                return aVal.localeCompare(bVal) * dir;
            });
            rows.forEach(row => tbody.appendChild(row));
        }

        // Cost basis editing with live P&L update
        document.querySelectorAll('.cost-input').forEach(input => {
            input.addEventListener('change', function() {
                const itemId = this.dataset.itemId;
                const cost = parseFloat(this.value) || 0;
                const price = parseFloat(this.dataset.currentPrice) || 0;

                // Update return display
                const cell = document.querySelector(`.pnl-cell[data-item-id="${itemId}"]`);
                if (cost > 0 && price > 0) {
                    const pnl = ((price - cost) / cost) * 100;
                    const cls = pnl >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400';
                    cell.innerHTML = `<span class="inline-flex items-center px-2 py-1 rounded-lg text-xs font-semibold ${cls}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)}%</span>`;
                } else {
                    cell.innerHTML = '<span class="text-gray-600 text-sm">—</span>';
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


@app.route('/api/items/<int:item_id>/history')
def get_item_history(item_id):
    """Get price history for a specific item."""
    database.init_db()
    history = database.get_price_history(item_id, limit=30)
    return jsonify({"history": history})


def run_server(host='127.0.0.1', port=5000, debug=False):
    app.run(host=host, port=port, debug=debug)
