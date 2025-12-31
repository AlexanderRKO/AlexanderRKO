"""
Web Dashboard - Browser-based portfolio visualization.

Provides a Flask-based web interface for viewing portfolio data.
Requires Flask: pip install flask
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from flask import Flask, render_template_string, jsonify, request, redirect, session, url_for
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None

# Xero OAuth integration
try:
    from .integrations import (
        XeroConfig, load_config, XeroOAuth, TokenStorage,
        XeroClient, AuthorizationError, TokenError,
    )
    XERO_AVAILABLE = True
except ImportError:
    XERO_AVAILABLE = False

from .models import Portfolio
from .storage import PortfolioDatabase
from .sector_lookup import get_sector_summary
from .analysis import PortfolioAnalyzer

logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"


def create_app() -> Optional["Flask"]:
    """Create and configure the Flask application."""
    if not FLASK_AVAILABLE:
        raise ImportError("Flask is required for web dashboard. Install with: pip install flask")

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    @app.route("/")
    def dashboard():
        """Main dashboard page."""
        db = PortfolioDatabase()
        db.initialize()
        portfolio = db.get_latest_portfolio()

        if not portfolio:
            return render_template_string(NO_DATA_TEMPLATE)

        # Prepare data for template
        context = prepare_dashboard_data(portfolio)
        return render_template_string(DASHBOARD_TEMPLATE, **context)

    @app.route("/api/portfolio")
    def api_portfolio():
        """API endpoint for portfolio data."""
        db = PortfolioDatabase()
        db.initialize()
        portfolio = db.get_latest_portfolio()

        if not portfolio:
            return jsonify({"error": "No portfolio data"}), 404

        return jsonify(portfolio.to_dict())

    @app.route("/api/sectors")
    def api_sectors():
        """API endpoint for sector breakdown."""
        db = PortfolioDatabase()
        db.initialize()
        portfolio = db.get_latest_portfolio()

        if not portfolio:
            return jsonify({"error": "No portfolio data"}), 404

        sectors = get_sector_summary(portfolio)
        return jsonify(sectors)

    @app.route("/api/holdings")
    def api_holdings():
        """API endpoint for holdings list."""
        db = PortfolioDatabase()
        db.initialize()
        portfolio = db.get_latest_portfolio()

        if not portfolio:
            return jsonify({"error": "No portfolio data"}), 404

        holdings = [h.to_dict() for h in portfolio.top_holdings]
        return jsonify(holdings)

    @app.route("/api/performance")
    def api_performance():
        """API endpoint for performance metrics."""
        db = PortfolioDatabase()
        db.initialize()
        portfolio = db.get_latest_portfolio()

        if not portfolio:
            return jsonify({"error": "No portfolio data"}), 404

        analyzer = PortfolioAnalyzer(portfolio)
        metrics = analyzer.get_summary_metrics()
        return jsonify(metrics)

    # ==========================================
    # Xero OAuth 2.0 Routes
    # ==========================================

    if XERO_AVAILABLE:
        # Store OAuth state in Flask session
        app.secret_key = app.secret_key or "portfolio-tracker-secret-change-in-production"

        @app.route("/xero")
        def xero_dashboard():
            """Xero integration dashboard."""
            config = load_config()
            storage = TokenStorage(config=config)
            storage.initialize()

            status = storage.get_status()
            tenants = storage.get_active_tenants()

            # Check if we have valid tokens
            has_valid_tokens = storage.has_valid_tokens()

            # Get tenant details with token status
            tenant_info = []
            for tenant in tenants:
                tenant_id = tenant.get("tenant_id")
                tokens = storage.get_tokens(tenant_id)
                tenant_info.append({
                    "name": tenant.get("tenant_name", "Unknown"),
                    "id": tenant_id,
                    "type": tenant.get("tenant_type", ""),
                    "tokens_valid": tokens and not tokens.is_expired if tokens else False,
                })

            return render_template_string(XERO_DASHBOARD_TEMPLATE,
                has_valid_tokens=has_valid_tokens,
                tenants=tenant_info,
                status=status,
                config_valid=config.is_valid(),
            )

        @app.route("/xero/auth")
        def xero_auth():
            """Start Xero OAuth flow."""
            config = load_config()

            if not config.is_valid():
                return jsonify({
                    "error": "Xero not configured",
                    "message": "Set XERO_CLIENT_ID and XERO_CLIENT_SECRET environment variables"
                }), 400

            oauth = XeroOAuth(config)

            # Generate authorization URL with PKCE
            auth_url, state = oauth.get_authorization_url()

            # Store state and code verifier in session for callback
            session["xero_state"] = state
            session["xero_code_verifier"] = oauth._code_verifier

            return redirect(auth_url)

        @app.route("/xero/callback")
        def xero_callback():
            """Handle Xero OAuth callback."""
            # Check for errors
            error = request.args.get("error")
            if error:
                error_description = request.args.get("error_description", "Unknown error")
                return render_template_string(XERO_ERROR_TEMPLATE,
                    error=error,
                    error_description=error_description,
                )

            # Get authorization code
            code = request.args.get("code")
            state = request.args.get("state")

            if not code:
                return render_template_string(XERO_ERROR_TEMPLATE,
                    error="missing_code",
                    error_description="No authorization code received",
                )

            # Verify state
            expected_state = session.get("xero_state")
            if state != expected_state:
                return render_template_string(XERO_ERROR_TEMPLATE,
                    error="invalid_state",
                    error_description="State mismatch - possible CSRF attack",
                )

            try:
                config = load_config()
                oauth = XeroOAuth(config)

                # Restore code verifier from session
                oauth._code_verifier = session.get("xero_code_verifier")
                oauth._state = expected_state

                # Exchange code for tokens
                tokens = oauth.exchange_code(code, state)

                # Get connected tenants
                tenants = oauth.get_connections(tokens.access_token)

                # Save tokens and tenants
                storage = TokenStorage(config=config)
                storage.initialize()

                for tenant in tenants:
                    storage.save_tokens(tokens, tenant.tenant_id, tenant.tenant_name)
                    storage.save_tenant(tenant)

                # Clear session state
                session.pop("xero_state", None)
                session.pop("xero_code_verifier", None)

                return render_template_string(XERO_SUCCESS_TEMPLATE,
                    tenants=tenants,
                    token_expires=tokens.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                )

            except (AuthorizationError, TokenError) as e:
                return render_template_string(XERO_ERROR_TEMPLATE,
                    error=type(e).__name__,
                    error_description=str(e),
                )

        @app.route("/xero/disconnect")
        def xero_disconnect():
            """Disconnect from Xero."""
            tenant_id = request.args.get("tenant")

            config = load_config()
            storage = TokenStorage(config=config)
            storage.initialize()

            if tenant_id:
                # Disconnect specific tenant
                tokens = storage.get_tokens(tenant_id)
                if tokens:
                    try:
                        oauth = XeroOAuth(config)
                        oauth.revoke_token(tokens.refresh_token)
                    except TokenError:
                        pass  # Continue with local cleanup
                storage.delete_tokens(tenant_id)
            else:
                # Disconnect all
                storage.delete_all_tokens()

            return redirect(url_for("xero_dashboard"))

        @app.route("/api/xero/status")
        def api_xero_status():
            """API endpoint for Xero status."""
            config = load_config()
            storage = TokenStorage(config=config)
            storage.initialize()

            return jsonify({
                "configured": config.is_valid(),
                "connected": storage.has_valid_tokens(),
                "status": storage.get_status(),
                "tenants": storage.get_active_tenants(),
            })

        @app.route("/api/xero/organisation")
        def api_xero_organisation():
            """API endpoint for Xero organisation details."""
            config = load_config()
            storage = TokenStorage(config=config)
            storage.initialize()

            tenant_id = request.args.get("tenant") or storage.get_default_tenant()
            if not tenant_id:
                return jsonify({"error": "No tenant connected"}), 404

            tokens = storage.get_tokens(tenant_id)
            if not tokens or tokens.is_expired:
                return jsonify({"error": "No valid tokens"}), 401

            try:
                client = XeroClient(config=config, tokens=tokens, tenant_id=tenant_id)
                org = client.get_organisation()
                return jsonify({
                    "id": org.organisation_id,
                    "name": org.name,
                    "legal_name": org.legal_name,
                    "country": org.country_code,
                    "currency": org.default_currency,
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    return app


def prepare_dashboard_data(portfolio: Portfolio) -> Dict[str, Any]:
    """Prepare data for the dashboard template."""
    # Get sector data
    sectors = get_sector_summary(portfolio)
    sector_labels = list(sectors.keys())
    sector_values = [float(s["market_value"]) for s in sectors.values()]
    sector_colors = [
        "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
        "#FF9F40", "#7CBA3D", "#E74C3C", "#3498DB", "#9B59B6",
        "#1ABC9C", "#34495E", "#95A5A6"
    ]

    # Top holdings
    top_holdings = portfolio.top_holdings[:10]

    # Performance data
    profitable = len(portfolio.profitable_holdings)
    losing = len(portfolio.losing_holdings)

    # Best and worst performers
    best = portfolio.best_performers[:5]
    worst = portfolio.worst_performers[:5]

    return {
        "portfolio": portfolio,
        "total_value": float(portfolio.total_market_value),
        "total_cost": float(portfolio.total_cost_base),
        "total_profit": float(portfolio.total_profit_loss),
        "profit_percent": float(portfolio.total_profit_loss_percent),
        "holding_count": portfolio.holding_count,
        "profitable_count": profitable,
        "losing_count": losing,
        "snapshot_date": portfolio.snapshot_date.isoformat(),
        "sector_labels": json.dumps(sector_labels),
        "sector_values": json.dumps(sector_values),
        "sector_colors": json.dumps(sector_colors[:len(sector_labels)]),
        "top_holdings": top_holdings,
        "best_performers": best,
        "worst_performers": worst,
        "sectors": sectors,
    }


def run_dashboard(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    """Run the dashboard server."""
    app = create_app()
    print(f"\n{'='*60}")
    print("PORTFOLIO DASHBOARD")
    print(f"{'='*60}")
    print(f"\n  Open in browser: http://{host}:{port}")
    print(f"\n  Press Ctrl+C to stop the server")
    print(f"{'='*60}\n")
    app.run(host=host, port=port, debug=debug)


# HTML Templates
NO_DATA_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Portfolio Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #1a1a2e; color: #eee; display: flex; justify-content: center;
               align-items: center; height: 100vh; margin: 0; }
        .message { text-align: center; }
        h1 { color: #ff6b6b; }
        p { color: #888; }
        code { background: #333; padding: 10px 20px; border-radius: 5px; display: inline-block; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="message">
        <h1>No Portfolio Data</h1>
        <p>Import a CommSec CSV file first:</p>
        <code>python -m portfolio_tracker import your_portfolio.csv</code>
    </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Portfolio Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f1a;
            color: #e0e0e0;
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 40px;
            border-bottom: 1px solid #333;
        }
        .header h1 { color: #fff; font-size: 24px; }
        .header .date { color: #888; font-size: 14px; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }

        /* Summary Cards */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: #1a1a2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #333;
        }
        .card-label { color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
        .card-value { font-size: 28px; font-weight: 600; margin-top: 5px; }
        .card-value.positive { color: #4ade80; }
        .card-value.negative { color: #f87171; }
        .card-sub { color: #666; font-size: 14px; margin-top: 5px; }

        /* Charts Section */
        .charts-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-card {
            background: #1a1a2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #333;
        }
        .chart-card h3 { margin-bottom: 15px; color: #fff; }
        .chart-container { position: relative; height: 300px; }

        /* Tables */
        .table-section { margin-bottom: 30px; }
        .table-section h3 { margin-bottom: 15px; color: #fff; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: #1a1a2e;
            border-radius: 12px;
            overflow: hidden;
        }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #16213e; color: #888; font-size: 12px; text-transform: uppercase; }
        tr:hover { background: #16213e; }
        .text-right { text-align: right; }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }

        /* Performance Grid */
        .perf-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .charts-grid, .perf-grid { grid-template-columns: 1fr; }
            .summary-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Portfolio Dashboard</h1>
        <div class="date">Snapshot: {{ snapshot_date }}</div>
    </div>

    <div class="container">
        <!-- Summary Cards -->
        <div class="summary-grid">
            <div class="card">
                <div class="card-label">Portfolio Value</div>
                <div class="card-value">${{ "{:,.0f}".format(total_value) }}</div>
                <div class="card-sub">{{ holding_count }} holdings</div>
            </div>
            <div class="card">
                <div class="card-label">Cost Base</div>
                <div class="card-value">${{ "{:,.0f}".format(total_cost) }}</div>
            </div>
            <div class="card">
                <div class="card-label">Total Profit/Loss</div>
                <div class="card-value {{ 'positive' if total_profit >= 0 else 'negative' }}">
                    ${{ "{:+,.0f}".format(total_profit) }}
                </div>
                <div class="card-sub {{ 'positive' if profit_percent >= 0 else 'negative' }}">
                    {{ "{:+.1f}".format(profit_percent) }}%
                </div>
            </div>
            <div class="card">
                <div class="card-label">Win/Loss Ratio</div>
                <div class="card-value">
                    <span class="positive">{{ profitable_count }}</span> /
                    <span class="negative">{{ losing_count }}</span>
                </div>
                <div class="card-sub">profitable / losing</div>
            </div>
        </div>

        <!-- Charts -->
        <div class="charts-grid">
            <div class="chart-card">
                <h3>Sector Allocation</h3>
                <div class="chart-container">
                    <canvas id="sectorChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>Top 10 Holdings</h3>
                <div class="chart-container">
                    <canvas id="holdingsChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Performance Tables -->
        <div class="perf-grid">
            <div class="table-section">
                <h3>🏆 Best Performers</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Code</th>
                            <th class="text-right">Value</th>
                            <th class="text-right">Return</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for h in best_performers %}
                        <tr>
                            <td><strong>{{ h.code }}</strong></td>
                            <td class="text-right">${{ "{:,.0f}".format(h.market_value) }}</td>
                            <td class="text-right positive">{{ "{:+.1f}".format(h.profit_loss_percent) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="table-section">
                <h3>📉 Worst Performers</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Code</th>
                            <th class="text-right">Value</th>
                            <th class="text-right">Return</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for h in worst_performers %}
                        <tr>
                            <td><strong>{{ h.code }}</strong></td>
                            <td class="text-right">${{ "{:,.0f}".format(h.market_value) }}</td>
                            <td class="text-right {{ 'positive' if h.profit_loss_percent >= 0 else 'negative' }}">
                                {{ "{:+.1f}".format(h.profit_loss_percent) }}%
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- All Holdings Table -->
        <div class="table-section">
            <h3>All Holdings</h3>
            <table>
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Name</th>
                        <th class="text-right">Qty</th>
                        <th class="text-right">Price</th>
                        <th class="text-right">Value</th>
                        <th class="text-right">Weight</th>
                        <th class="text-right">P/L</th>
                        <th class="text-right">Return</th>
                    </tr>
                </thead>
                <tbody>
                    {% for h in top_holdings %}
                    <tr>
                        <td><strong>{{ h.code }}</strong></td>
                        <td>{{ h.name[:30] }}</td>
                        <td class="text-right">{{ "{:,}".format(h.quantity) }}</td>
                        <td class="text-right">${{ "{:.2f}".format(h.current_price) }}</td>
                        <td class="text-right">${{ "{:,.0f}".format(h.market_value) }}</td>
                        <td class="text-right">{{ "{:.1f}".format(h.portfolio_weight) }}%</td>
                        <td class="text-right {{ 'positive' if h.profit_loss >= 0 else 'negative' }}">
                            ${{ "{:+,.0f}".format(h.profit_loss) }}
                        </td>
                        <td class="text-right {{ 'positive' if h.profit_loss_percent >= 0 else 'negative' }}">
                            {{ "{:+.1f}".format(h.profit_loss_percent) }}%
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // Sector Pie Chart
        const sectorCtx = document.getElementById('sectorChart').getContext('2d');
        new Chart(sectorCtx, {
            type: 'doughnut',
            data: {
                labels: {{ sector_labels|safe }},
                datasets: [{
                    data: {{ sector_values|safe }},
                    backgroundColor: {{ sector_colors|safe }},
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { color: '#888', boxWidth: 12, padding: 10 }
                    }
                }
            }
        });

        // Top Holdings Bar Chart
        const holdingsCtx = document.getElementById('holdingsChart').getContext('2d');
        const holdingsData = [
            {% for h in top_holdings %}
            { code: '{{ h.code }}', value: {{ h.market_value|float }} },
            {% endfor %}
        ];
        new Chart(holdingsCtx, {
            type: 'bar',
            data: {
                labels: holdingsData.map(h => h.code),
                datasets: [{
                    label: 'Value',
                    data: holdingsData.map(h => h.value),
                    backgroundColor: '#36A2EB',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#888',
                            callback: function(value) { return '$' + value.toLocaleString(); }
                        },
                        grid: { color: '#333' }
                    },
                    y: {
                        ticks: { color: '#888' },
                        grid: { display: false }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

# Xero OAuth 2.0 Templates
XERO_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Xero Integration - Portfolio Tracker</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; color: #eee; padding: 30px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #00c8ff; margin-bottom: 30px; }
        h2 { color: #888; font-size: 1.2em; margin: 30px 0 15px; }
        .card {
            background: #252540; border-radius: 12px; padding: 25px;
            margin-bottom: 20px;
        }
        .status-connected { color: #4ade80; }
        .status-disconnected { color: #f87171; }
        .status-warning { color: #fbbf24; }
        .btn {
            display: inline-block; padding: 12px 24px;
            background: #00c8ff; color: #000; font-weight: 600;
            border-radius: 8px; text-decoration: none;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.8; }
        .btn-danger { background: #f87171; }
        .btn-secondary { background: #4a4a6a; color: #fff; }
        .tenant-list { list-style: none; }
        .tenant-item {
            display: flex; justify-content: space-between;
            align-items: center; padding: 15px;
            background: #1a1a2e; border-radius: 8px;
            margin-bottom: 10px;
        }
        .tenant-name { font-weight: 600; }
        .tenant-type { color: #888; font-size: 0.9em; }
        .info-row { display: flex; justify-content: space-between; padding: 8px 0; }
        .info-label { color: #888; }
        a { color: #00c8ff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Xero Integration</h1>

        <div class="card">
            <h2 style="margin-top: 0;">Connection Status</h2>
            {% if not config_valid %}
            <p class="status-warning">Xero not configured</p>
            <p style="color: #888; margin-top: 10px;">
                Set XERO_CLIENT_ID and XERO_CLIENT_SECRET environment variables.
            </p>
            {% elif has_valid_tokens %}
            <p class="status-connected">Connected</p>
            {% else %}
            <p class="status-disconnected">Not Connected</p>
            <a href="/xero/auth" class="btn" style="margin-top: 15px;">Connect to Xero</a>
            {% endif %}
        </div>

        {% if tenants %}
        <div class="card">
            <h2 style="margin-top: 0;">Connected Organisations</h2>
            <ul class="tenant-list">
                {% for tenant in tenants %}
                <li class="tenant-item">
                    <div>
                        <div class="tenant-name">{{ tenant.name }}</div>
                        <div class="tenant-type">{{ tenant.type }}</div>
                    </div>
                    <div>
                        {% if tenant.tokens_valid %}
                        <span class="status-connected">Active</span>
                        {% else %}
                        <span class="status-warning">Expired</span>
                        {% endif %}
                        <a href="/xero/disconnect?tenant={{ tenant.id }}"
                           class="btn btn-secondary" style="margin-left: 10px; padding: 8px 16px;">
                            Disconnect
                        </a>
                    </div>
                </li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}

        <div class="card">
            <h2 style="margin-top: 0;">Storage Info</h2>
            <div class="info-row">
                <span class="info-label">Database</span>
                <span>{{ status.db_path }}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Encryption</span>
                <span>{{ 'Enabled' if status.encryption_enabled else 'Disabled' }}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Token Records</span>
                <span>{{ status.token_count }}</span>
            </div>
        </div>

        <p style="margin-top: 30px;">
            <a href="/">&larr; Back to Dashboard</a>
        </p>
    </div>
</body>
</html>
"""

XERO_SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Connected to Xero - Portfolio Tracker</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; color: #eee;
            display: flex; justify-content: center; align-items: center;
            height: 100vh; margin: 0;
        }
        .message { text-align: center; max-width: 500px; padding: 40px; }
        h1 { color: #4ade80; margin-bottom: 20px; }
        p { color: #888; line-height: 1.6; }
        .tenant-list { list-style: none; padding: 0; margin: 20px 0; }
        .tenant-item {
            background: #252540; padding: 15px 20px;
            border-radius: 8px; margin-bottom: 10px;
        }
        .btn {
            display: inline-block; padding: 12px 24px;
            background: #00c8ff; color: #000; font-weight: 600;
            border-radius: 8px; text-decoration: none;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="message">
        <h1>Successfully Connected!</h1>
        <p>You have connected the following Xero organisations:</p>
        <ul class="tenant-list">
            {% for tenant in tenants %}
            <li class="tenant-item">
                <strong>{{ tenant.tenant_name }}</strong>
                <br><small style="color: #888;">{{ tenant.tenant_type }}</small>
            </li>
            {% endfor %}
        </ul>
        <p>Access token expires: {{ token_expires }} UTC</p>
        <a href="/xero" class="btn">View Xero Dashboard</a>
    </div>
</body>
</html>
"""

XERO_ERROR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Xero Error - Portfolio Tracker</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; color: #eee;
            display: flex; justify-content: center; align-items: center;
            height: 100vh; margin: 0;
        }
        .message { text-align: center; max-width: 500px; padding: 40px; }
        h1 { color: #f87171; margin-bottom: 20px; }
        p { color: #888; line-height: 1.6; }
        .error-code { color: #fbbf24; font-family: monospace; }
        .btn {
            display: inline-block; padding: 12px 24px;
            background: #4a4a6a; color: #fff; font-weight: 600;
            border-radius: 8px; text-decoration: none;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="message">
        <h1>Authorization Failed</h1>
        <p class="error-code">{{ error }}</p>
        <p>{{ error_description }}</p>
        <a href="/xero" class="btn">Try Again</a>
    </div>
</body>
</html>
"""
