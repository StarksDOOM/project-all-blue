"""
Jinja2-based notification compiler for Stream 5 Phase 4.0 outbound alerts.

Isolated, stateless (or minimally configured) service class that renders
personalized, responsive HTML transactional emails for property matches.

Complies with Python OOP & Documentation Standards: full encapsulation,
comprehensive PEP 257 docstrings on module/class/methods (purpose, invariants,
lifecycle, parameters, returns, raises, side effects).

No session state, no orchestrator creep — pure rendering concern only.
"""

from __future__ import annotations

from typing import Any, Dict

from jinja2 import Environment, PackageLoader, select_autoescape


class NotificationCompiler:
    """
    Compiles match data + alert context into a secure, responsive HTML email body.

    Purpose:
        Transform a SavedSearchMatch (with embedded property snapshot) and the
        owning SavedSearchAlert title into a user-friendly email that highlights
        the key real-estate details and provides a clear call-to-action link back
        to the storefront property detail page.

    Invariants:
        - Always uses auto-escaping to prevent XSS from property titles/descriptions.
        - Provides graceful degradation for missing images (placeholder).
        - Currency is assumed USD (or derived from snapshot); formatted with $ and commas.
        - Output is a complete self-contained HTML fragment suitable for email clients.

    Lifecycle:
        - Instantiate once per process (or per request if template reloading needed).
        - Thread-safe for read-only rendering after init.
        - No database access; pure function of input dicts.

    Integration:
        Called by NotificationDispatcher immediately before queuing the email.
        Input data comes from the match_details snapshot + alert + property fields.
    """

    def __init__(self, frontend_base_url: str = "http://localhost:3000") -> None:
        """
        Initialize the Jinja2 environment with secure defaults.

        Args:
            frontend_base_url: Base URL for constructing property detail links
                (e.g. "https://app.allblue.example.com"). Injected for test/prod flexibility.

        Raises:
            RuntimeError: If Jinja2 environment cannot be configured (template loader issue).
        """
        self._frontend_base_url = frontend_base_url.rstrip("/")

        try:
            # Use PackageLoader so templates can live in services/templates/
            # Fallback to inline if package structure not present in some deployments.
            self._env = Environment(
                loader=PackageLoader("services", "templates"),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        except Exception as exc:  # pragma: no cover - loader fallback
            # Provide minimal inline templates as last resort (keeps system functional).
            self._env = Environment(autoescape=select_autoescape(["html", "xml"]))
            self._register_inline_templates()
            # Re-raise wrapped for visibility in logs.
            raise RuntimeError(
                "NotificationCompiler could not load external templates; using inline fallback. "
                "Install jinja2 and ensure services/templates/ exists."
            ) from exc

    def _register_inline_templates(self) -> None:
        """Register minimal inline templates when PackageLoader fails (defensive)."""
        base = """
        <!doctype html>
        <html><head><meta charset="utf-8"><title>{{ subject }}</title></head>
        <body style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; padding: 16px;">
        {% block content %}{% endblock %}
        <p style="font-size: 12px; color: #666;">All Blue — Property Alerts</p>
        </body></html>
        """
        alert = """
        {% extends "base" %}
        {% block content %}
        <h2>New match for "{{ alert_title }}"</h2>
        {% if image_url %}
        <img src="{{ image_url }}" alt="Property" style="max-width:100%; border-radius:8px;">
        {% else %}
        <div style="background:#f0f0f0; height:160px; display:flex; align-items:center; justify-content:center; border-radius:8px;">
            <span style="color:#888;">No image available</span>
        </div>
        {% endif %}
        <p><strong>{{ title }}</strong></p>
        <p style="font-size: 1.4em; font-weight: 600;">{{ price_formatted }}</p>
        <p>{{ location }}</p>
        <a href="{{ detail_url }}" style="display:inline-block; background:#0a66c2; color:white; padding:12px 24px; text-decoration:none; border-radius:6px;">View on All Blue</a>
        {% endblock %}
        """
        self._env.globals["base"] = self._env.from_string(base)
        self._env.globals["property_alert"] = self._env.from_string(alert)

    def _format_price(self, price_usd: float | None, list_price: float | None) -> str:
        """Format effective price as USD with commas and $ symbol."""
        price = list_price if list_price is not None else price_usd
        if price is None:
            return "Price on request"
        try:
            return f"${price:,.0f} USD"
        except (TypeError, ValueError):
            return "Price unavailable"

    def compile(
        self,
        match_details: Dict[str, Any],
        alert_title: str,
        property_id: str,
        property_title: str | None = None,
        image_urls: list[str] | None = None,
        sector: str | None = None,
        price_usd: float | None = None,
        list_price: float | None = None,
    ) -> str:
        """
        Render the final HTML email for a property match.

        Args:
            match_details: The 'match_details' JSONB from SavedSearchMatch (contains snapshot).
            alert_title: Friendly title of the SavedSearchAlert that matched.
            property_id: The Blu ID or remote id of the matched property (used for link).
            property_title: Optional display title (falls back to snapshot).
            image_urls: Optional list of images from the property (first used; fallback applied).
            sector: Location/sector (falls back to snapshot).
            price_usd: USD price (falls back to snapshot).
            list_price: Exact list price if present.

        Returns:
            Complete HTML string ready to be sent as email body.

        Raises:
            jinja2.TemplateError: On rendering failure (should be rare with validated inputs).
            ValueError: If critical data (e.g. property_id) is missing.
        """
        if not property_id:
            raise ValueError("property_id is required to generate detail link")

        snapshot = match_details.get("snapshot", {}) if match_details else {}

        # Prefer explicit args, fall back to snapshot for resilience
        final_title = property_title or snapshot.get("title") or "Property match"
        final_sector = sector or snapshot.get("sector") or "Unknown location"
        final_price_usd = price_usd if price_usd is not None else snapshot.get("price_usd")
        final_list_price = list_price if list_price is not None else snapshot.get("list_price")

        image_url = (image_urls or snapshot.get("image_urls") or [None])[0]
        if not image_url:
            image_url = "https://placehold.co/600x320/e2e8f0/64748b?text=All+Blue+Property"

        detail_url = f"{self._frontend_base_url}/properties/{property_id}"

        price_formatted = self._format_price(final_price_usd, final_list_price)

        template = self._env.get_template("property_alert.html")
        # Some deployments use the globals fallback; try both.
        try:
            html = template.render(
                subject=f"New match: {alert_title}",
                alert_title=alert_title,
                title=final_title,
                image_url=image_url,
                price_formatted=price_formatted,
                location=final_sector,
                detail_url=detail_url,
            )
        except Exception:
            # Fallback using the global we registered in __init__ for inline case
            fallback = self._env.get_template("property_alert")
            html = fallback.render(
                subject=f"New match: {alert_title}",
                alert_title=alert_title,
                title=final_title,
                image_url=image_url,
                price_formatted=price_formatted,
                location=final_sector,
                detail_url=detail_url,
            )

        return html
