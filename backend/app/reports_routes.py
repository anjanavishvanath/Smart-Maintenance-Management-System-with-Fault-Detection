from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import get_jwt_identity, get_jwt
from db import get_asset_reliability_report, get_alert_resolution_report, get_fft_deep_dive, get_asset_details
import csv
from io import StringIO


def _parse_iso_dt(value):
    """Parse an ISO-8601 string from a query param. Accepts '...Z' suffix.
    Returns a timezone-aware datetime, or None if the string is missing/invalid."""
    if not value:
        return None
    try:
        # Python <3.11 fromisoformat doesn't accept the 'Z' suffix; normalise it.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _date_range_from_request():
    """Pull from/to ISO timestamps from the request, return (from_dt, to_dt) or (None, None)."""
    return _parse_iso_dt(request.args.get("from")), _parse_iso_dt(request.args.get("to"))


def get_reliability_report_route():
    claims = get_jwt()
    organization = claims.get('organization')
    if not organization:
        return jsonify({"error": "Organization not found in token"}), 400
    from_ts, to_ts = _date_range_from_request()
    report = get_asset_reliability_report(organization, from_ts=from_ts, to_ts=to_ts)
    return jsonify(report), 200


def get_alert_resolution_report_route():
    claims = get_jwt()
    organization = claims.get('organization')
    if not organization:
        return jsonify({"error": "Organization not found in token"}), 400
    from_ts, to_ts = _date_range_from_request()
    report = get_alert_resolution_report(organization, from_ts=from_ts, to_ts=to_ts)
    return jsonify(report), 200


def _csv_response(rows, header, filename):
    """Render an iterable of dict-like rows as a CSV download response."""
    buf = StringIO()
    cw = csv.writer(buf)
    cw.writerow(header)
    for r in rows:
        cw.writerow([r.get(col, "") for col in header])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"},
    )


def get_reliability_export_route():
    """CSV export of the reliability report for the caller's organization."""
    claims = get_jwt() or {}
    organization = claims.get("organization")
    if not organization:
        return jsonify({"error": "Organization not found in token"}), 400
    from_ts, to_ts = _date_range_from_request()
    report = get_asset_reliability_report(organization, from_ts=from_ts, to_ts=to_ts)
    header = [
        "asset_id", "asset_name", "uptime_percentage",
        "critical_alert_count", "critical_downtime_sec",
        "condition_score", "diagnosis",
    ]
    return _csv_response(report, header, "reliability_report.csv")


def get_alert_resolution_export_route():
    """CSV export of the alert resolution / maintenance audit for the caller's organization."""
    claims = get_jwt() or {}
    organization = claims.get("organization")
    if not organization:
        return jsonify({"error": "Organization not found in token"}), 400
    from_ts, to_ts = _date_range_from_request()
    report = get_alert_resolution_report(organization, from_ts=from_ts, to_ts=to_ts)
    header = [
        "ticket_id", "asset_name", "diagnosis",
        "status", "timestamp", "resolved_at", "response_time_hours",
    ]
    return _csv_response(report, header, "alert_resolution_report.csv")


def get_fft_export_route(asset_id: int):
    """Export FFT deep-dive as CSV. Org-scoped: caller must own the asset's organization."""
    claims = get_jwt() or {}
    organization = (claims.get("organization") or "").strip()
    if not organization:
        return jsonify({"error": "Organization not found in token"}), 400

    asset = get_asset_details(asset_id)
    if not asset or (asset.get("organization") or "").strip() != organization:
        # Same response whether the asset doesn't exist or belongs to another org —
        # don't leak existence to outsiders.
        return jsonify({"error": "Asset not found in your organization"}), 404

    from_ts, to_ts = _date_range_from_request()
    report = get_fft_deep_dive(asset_id, from_ts=from_ts, to_ts=to_ts)

    header = ['timestamp', 'axis', 'dominant_freq_hz', 'rms_velocity', 'rms_z_score', 'freq_z_score']
    return _csv_response(report, header, f"fft_analysis_asset_{asset_id}.csv")
