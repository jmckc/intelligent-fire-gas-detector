"""
server/models/database.py
SQLAlchemy models
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


def init_db():
    db.create_all()
    if Contact.query.count() == 0:
        db.session.add(Contact(name="Admin", phone="+10000000000", email="admin@example.com"))
        db.session.commit()


class SensorReading(db.Model):
    __tablename__ = "sensor_readings"
    id             = db.Column(db.Integer,  primary_key=True)
    timestamp      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    gas_adc        = db.Column(db.Integer,  nullable=False)
    gas_rate_pct   = db.Column(db.Float,    default=0.0)
    temperature    = db.Column(db.Float,    nullable=True)
    humidity       = db.Column(db.Float,    nullable=True)
    flame_detected = db.Column(db.Boolean,  default=False)
    gas_alarm      = db.Column(db.Boolean,  default=False)
    temp_alarm     = db.Column(db.Boolean,  default=False)
    alarm          = db.Column(db.Boolean,  default=False)

    def to_dict(self):
        return {
            "id":             self.id,
            "timestamp":      self.timestamp.isoformat(),
            "gas_adc":        self.gas_adc,
            "gas_rate_pct":   self.gas_rate_pct,
            "temperature":    self.temperature,
            "humidity":       self.humidity,
            "flame_detected": self.flame_detected,
            "gas_alarm":      self.gas_alarm,
            "temp_alarm":     self.temp_alarm,
            "alarm":          self.alarm,
        }


class AlertEvent(db.Model):
    __tablename__ = "alert_events"
    id             = db.Column(db.Integer,     primary_key=True)
    timestamp      = db.Column(db.DateTime,    default=datetime.utcnow, index=True)
    severity       = db.Column(db.String(20),  default="HIGH")
    trigger_reason = db.Column(db.String(100), nullable=True)
    ai_decision    = db.Column(db.String(30),  nullable=True)
    ai_confidence  = db.Column(db.Float,       nullable=True)
    ai_reasoning   = db.Column(db.Text,        nullable=True)
    sms_sent       = db.Column(db.Boolean,     default=False)
    email_sent     = db.Column(db.Boolean,     default=False)
    acknowledged   = db.Column(db.Boolean,     default=False)
    ack_notes      = db.Column(db.Text,        nullable=True)

    def to_dict(self):
        return {
            "id":             self.id,
            "timestamp":      self.timestamp.isoformat(),
            "severity":       self.severity,
            "trigger_reason": self.trigger_reason,
            "ai_decision":    self.ai_decision,
            "ai_confidence":  self.ai_confidence,
            "ai_reasoning":   self.ai_reasoning,
            "sms_sent":       self.sms_sent,
            "email_sent":     self.email_sent,
            "acknowledged":   self.acknowledged,
            "ack_notes":      self.ack_notes,
        }


class Contact(db.Model):
    __tablename__ = "contacts"
    id     = db.Column(db.Integer,     primary_key=True)
    name   = db.Column(db.String(80),  nullable=False)
    phone  = db.Column(db.String(30),  nullable=True)
    email  = db.Column(db.String(120), nullable=True)
    active = db.Column(db.Boolean,     default=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name,
                "phone": self.phone, "email": self.email, "active": self.active}
