"""
server/routes/api.py
REST API endpoints
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
from server.models.database import db, SensorReading, AlertEvent, Contact
from server.services.ai_analyzer import analyze_with_llm
from server.services.notifier    import dispatch_notifications
from datetime import datetime, timedelta
import json, time

api_bp = Blueprint("api", __name__)
_sse_clients: list = []


@api_bp.route("/sensor-data", methods=["POST"])
def receive_sensor_data():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    reading = SensorReading(
        gas_adc        = data.get("gas",     0),
        gas_rate_pct   = data.get("gas_rate", 0.0),
        temperature    = data.get("temp"),
        humidity       = data.get("hum"),
        flame_detected = data.get("flame",   False),
        gas_alarm      = data.get("gas_al",  False),
        temp_alarm     = data.get("tmp_al",  False),
        alarm          = data.get("alarm",   False),
    )
    db.session.add(reading)
    db.session.commit()

    cutoff = datetime.utcnow() - timedelta(hours=24)
    SensorReading.query.filter(SensorReading.timestamp < cutoff).delete()
    db.session.commit()

    _broadcast_sse(reading.to_dict())

    if reading.alarm:
        _handle_alarm(reading)

    return jsonify({"status": "ok", "id": reading.id}), 201


@api_bp.route("/status", methods=["GET"])
def get_status():
    latest = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
    if not latest:
        return jsonify({"status": "no_data"}), 200
    return jsonify({"status": "ok", "latest": latest.to_dict()})


@api_bp.route("/events", methods=["GET"])
def get_events():
    page  = request.args.get("page",  1,  type=int)
    limit = request.args.get("limit", 20, type=int)
    events = (AlertEvent.query
              .order_by(AlertEvent.timestamp.desc())
              .paginate(page=page, per_page=limit, error_out=False))
    return jsonify({
        "events": [e.to_dict() for e in events.items],
        "total":  events.total,
        "page":   page,
        "pages":  events.pages,
    })


@api_bp.route("/readings", methods=["GET"])
def get_readings():
    n = request.args.get("n", 60, type=int)
    rows = (SensorReading.query
            .order_by(SensorReading.timestamp.desc())
            .limit(n).all())
    return jsonify([r.to_dict() for r in reversed(rows)])


@api_bp.route("/acknowledge", methods=["POST"])
def acknowledge_event():
    body     = request.get_json(silent=True) or {}
    event_id = body.get("event_id")
    notes    = body.get("notes", "")
    event = AlertEvent.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    event.acknowledged = True
    event.ack_notes    = notes
    db.session.commit()
    return jsonify({"status": "acknowledged", "event_id": event_id})


@api_bp.route("/stream", methods=["GET"])
def stream():
    def event_generator():
        q = []
        _sse_clients.append(q)
        try:
            yield "data: {\"connected\": true}\n\n"
            while True:
                if q:
                    payload = q.pop(0)
                    yield f"data: {json.dumps(payload)}\n\n"
                else:
                    yield ": heartbeat\n\n"
                time.sleep(1)
        except GeneratorExit:
            _sse_clients.remove(q)

    return Response(
        stream_with_context(event_generator()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _broadcast_sse(payload: dict):
    for q in _sse_clients:
        q.append(payload)


def _handle_alarm(reading: SensorReading):
    recent  = (SensorReading.query.order_by(SensorReading.timestamp.desc()).limit(60).all())
    history = [r.to_dict() for r in reversed(recent)]

    reasons = []
    if reading.gas_alarm:      reasons.append("gas")
    if reading.flame_detected: reasons.append("flame")
    if reading.temp_alarm:     reasons.append("temperature")
    trigger = "+".join(reasons) if reasons else "unknown"

    ai_result = analyze_with_llm(reading.to_dict(), history)

    event = AlertEvent(
        trigger_reason = trigger,
        ai_decision    = ai_result["decision"],
        ai_confidence  = ai_result["confidence"],
        ai_reasoning   = ai_result["reasoning"],
        severity       = "HIGH" if ai_result["decision"] == "GENUINE_EMERGENCY" else "LOW",
    )
    db.session.add(event)
    db.session.commit()

    if ai_result["decision"] == "GENUINE_EMERGENCY" and ai_result["confidence"] >= 0.85:
        notif = dispatch_notifications(event, reading)
        event.sms_sent   = notif.get("sms",   False)
        event.email_sent = notif.get("email", False)
        db.session.commit()
