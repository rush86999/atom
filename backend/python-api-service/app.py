"""
ATOM - Advanced Task Orchestration & Management Backend API
Flask application with PostgreSQL, WebSocket support, and comprehensive integrations
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

# Determine async mode based on environment
async_mode = 'gevent' if os.getenv('FLASK_ENV') == 'production' else 'threading'
socketio = SocketIO(async_mode=async_mode, cors_allowed_origins="*")

def create_app(config_name='development'):
    """Application factory pattern"""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)

    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL',
        'postgresql://atom_user:atom_password@localhost:5432/atom_db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    socketio.init_app(app, message_queue=os.getenv('REDIS_URL'))

    # Enable CORS with environment-based origins
    from .config import get_config
    config = get_config(config_name)
    cors_origins = config.CORS_ORIGINS if hasattr(config, 'CORS_ORIGINS') else ["http://localhost:3000", "http://localhost:5173"]

    CORS(app, resources={
        r"/api/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })

    # Logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.tasks import tasks_bp
    from .routes.calendar import calendar_bp
    from .routes.communications import communications_bp
    from .routes.integrations import integrations_bp
    from .routes.workflows import workflows_bp
    from .routes.agents import agents_bp
    from .routes.finances import finances_bp
    from .routes.voice import voice_bp
    from .routes.health import health_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(calendar_bp, url_prefix='/api/calendar')
    app.register_blueprint(communications_bp, url_prefix='/api/communications')
    app.register_blueprint(integrations_bp, url_prefix='/api/integrations')
    app.register_blueprint(workflows_bp, url_prefix='/api/workflows')
    app.register_blueprint(agents_bp, url_prefix='/api/agents')
    app.register_blueprint(finances_bp, url_prefix='/api/finances')
    app.register_blueprint(voice_bp, url_prefix='/api/voice')
    app.register_blueprint(health_bp, url_prefix='/api/health')

    # Error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad Request', 'message': str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized', 'message': str(error)}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden', 'message': str(error)}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not Found', 'message': str(error)}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(error)}), 500

    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })

    # Request logging
    @app.before_request
    def log_request_info():
        app.logger.info(f'{request.method} {request.url} - {request.remote_addr}')

    # Database connection cleanup
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    return app

# Socket.IO event handlers with enhanced error handling and logging
logger = logging.getLogger(__name__)

@socketio.on('connect')
def handle_connect():
    try:
        logger.info(f'WebSocket client connected: {request.sid} from {request.remote_addr}')
        emit('connected', {
            'status': 'success',
            'sid': request.sid,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f'Error handling WebSocket connect: {str(e)}')
        disconnect()

@socketio.on('disconnect')
def handle_disconnect():
    try:
        logger.info(f'WebSocket client disconnected: {request.sid}')
        # Clean up any room memberships or session data here
    except Exception as e:
        logger.error(f'Error handling WebSocket disconnect: {str(e)}')

@socketio.on('join')
def handle_join(data):
    try:
        if not isinstance(data, dict):
            emit('error', {'message': 'Invalid join data format'})
            return

        room = data.get('room')
        if not room:
            emit('error', {'message': 'Room name required'})
            return

        join_room(room)
        logger.info(f'Client {request.sid} joined room: {room}')
        emit('joined', {
            'room': room,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f'Error handling join room: {str(e)}')
        emit('error', {'message': 'Failed to join room'})

@socketio.on('leave')
def handle_leave(data):
    try:
        if not isinstance(data, dict):
            emit('error', {'message': 'Invalid leave data format'})
            return

        room = data.get('room')
        if not room:
            emit('error', {'message': 'Room name required'})
            return

        leave_room(room)
        logger.info(f'Client {request.sid} left room: {room}')
        emit('left', {
            'room': room,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f'Error handling leave room: {str(e)}')
        emit('error', {'message': 'Failed to leave room'})

@socketio.on('ping')
def handle_ping():
    """Heartbeat mechanism"""
    try:
        emit('pong', {'timestamp': datetime.utcnow().isoformat()})
    except Exception as e:
        logger.error(f'Error handling ping: {str(e)}')

@socketio.on_error
def handle_socket_error(e):
    """Global error handler for Socket.IO events"""
    logger.error(f'Socket.IO error for client {request.sid}: {str(e)}')
    emit('error', {'message': 'Internal server error'})

# Import models after app creation to avoid circular imports
from . import models

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=3001, debug=True)
