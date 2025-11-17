"""
Database models for ATOM application
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    # Profile data
    preferences = db.Column(db.JSON, default=dict)
    advanced_settings = db.Column(db.JSON, default=dict)

    # Relationships
    tasks = db.relationship('Task', backref='user', lazy=True)
    messages = db.relationship('Message', backref='user', lazy=True)
    calendar_events = db.relationship('CalendarEvent', backref='user', lazy=True)
    integrations = db.relationship('Integration', backref='user', lazy=True)
    workflows = db.relationship('Workflow', backref='user', lazy=True)
    notes = db.relationship('Note', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    voice_commands = db.relationship('VoiceCommand', backref='user', lazy=True)
    agent_logs = db.relationship('AgentLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'preferences': self.preferences,
            'advanced_settings': self.advanced_settings,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    due_date = db.Column(db.DateTime)
    is_important = db.Column(db.Boolean, default=False)
    assignee = db.Column(db.String(100))
    tags = db.Column(db.JSON, default=list)
    subtasks = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'is_important': self.is_important,
            'assignee': self.assignee,
            'tags': self.tags,
            'subtasks': self.subtasks,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    color = db.Column(db.String(20), default='blue')
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    attendees = db.Column(db.JSON, default=list)
    recurrence = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'color': self.color,
            'description': self.description,
            'location': self.location,
            'attendees': self.attendees,
            'recurrence': self.recurrence,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)  # gmail, slack, teams, etc.
    from_name = db.Column(db.String(100))
    from_email = db.Column(db.String(120))
    subject = db.Column(db.String(200))
    preview = db.Column(db.Text)
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, nullable=False)
    unread = db.Column(db.Boolean, default=True)
    read = db.Column(db.Boolean, default=False)
    labels = db.Column(db.JSON, default=list)
    attachments = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'from': {
                'name': self.from_name,
                'email': self.from_email
            },
            'subject': self.subject,
            'preview': self.preview,
            'body': self.body,
            'timestamp': self.timestamp.isoformat(),
            'unread': self.unread,
            'read': self.read,
            'labels': self.labels,
            'attachments': self.attachments
        }

class Integration(db.Model):
    __tablename__ = 'integrations'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    connected = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20))  # success, failed, in_progress
    config = db.Column(db.JSON, default=dict)
    dev_status = db.Column(db.String(20), default='planned')  # implemented, development, planned
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'display_name': self.display_name,
            'service_type': self.service_type,
            'category': self.category,
            'connected': self.connected,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'sync_status': self.sync_status,
            'dev_status': self.dev_status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Workflow(db.Model):
    __tablename__ = 'workflows'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    enabled = db.Column(db.Boolean, default=True)
    triggers = db.Column(db.JSON, default=list)
    actions = db.Column(db.JSON, default=list)
    execution_count = db.Column(db.Integer, default=0)
    last_executed = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'triggers': self.triggers,
            'actions': self.actions,
            'execution_count': self.execution_count,
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='personal_memo')
    event_id = db.Column(db.String(36))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'type': self.type,
            'event_id': self.event_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # debit, credit
    account = db.Column(db.String(50))
    tags = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'description': self.description,
            'amount': self.amount,
            'category': self.category,
            'type': self.type,
            'account': self.account,
            'tags': self.tags
        }

class VoiceCommand(db.Model):
    __tablename__ = 'voice_commands'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    phrase = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    enabled = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    average_confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'phrase': self.phrase,
            'description': self.description,
            'enabled': self.enabled,
            'usage_count': self.usage_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'average_confidence': self.average_confidence,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class AgentLog(db.Model):
    __tablename__ = 'agent_logs'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    agent_name = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(20), default='info')  # info, warning, error
    message = db.Column(db.Text, nullable=False)
    log_metadata = db.Column(db.JSON, default=dict)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'level': self.level,
            'message': self.message,
            'metadata': self.log_metadata,
            'timestamp': self.timestamp.isoformat()
        }

class DevProject(db.Model):
    __tablename__ = 'dev_projects'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='building')  # building, live, error
    progress = db.Column(db.Integer, default=0)
    live_url = db.Column(db.String(200))
    preview_url = db.Column(db.String(200))
    metrics = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'progress': self.progress,
            'live_url': self.live_url,
            'preview_url': self.preview_url,
            'metrics': self.metrics,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# Create all tables
def create_tables():
    db.create_all()

# Drop all tables
def drop_tables():
    db.drop_all()
