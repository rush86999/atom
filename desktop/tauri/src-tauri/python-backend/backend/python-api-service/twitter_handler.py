import logging
from flask import Blueprint, request, jsonify, current_app
from . import twitter_service

logger = logging.getLogger(__name__)

twitter_bp = Blueprint('twitter_bp', __name__)

@twitter_bp.route('/api/twitter/timeline', methods=['GET'])
async def get_timeline():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
        if not api:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Twitter client. Please connect your Twitter account."}}), 401

        timeline = await twitter_service.get_timeline(api)
        return jsonify({"ok": True, "data": {"tweets": timeline}})
    except Exception as e:
        logger.error(f"Error getting Twitter timeline for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TIMELINE_FETCH_FAILED", "message": str(e)}}), 500

@twitter_bp.route('/api/twitter/tweet', methods=['POST'])
async def post_tweet():
    data = request.get_json()
    user_id = data.get('user_id')
    status = data.get('status')
    if not user_id or not status:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and status are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
        if not api:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Twitter client. Please connect your Twitter account."}}), 401

        tweet = await twitter_service.post_tweet(api, status)
        return jsonify({"ok": True, "data": tweet})
    except Exception as e:
        logger.error(f"Error posting tweet for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TWEET_POST_FAILED", "message": str(e)}}), 500

@twitter_bp.route('/api/twitter/search', methods=['GET'])
async def search_tweets():
    user_id = request.args.get('user_id')
    query = request.args.get('q')
    if not user_id or not query:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and q are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
        if not api:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Twitter client. Please connect your Twitter account."}}), 401

        tweets = await twitter_service.search_tweets(api, query)
        return jsonify({"ok": True, "data": {"tweets": tweets}})
    except Exception as e:
        logger.error(f"Error searching tweets for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TWEET_SEARCH_FAILED", "message": str(e)}}), 500

@twitter_bp.route('/api/twitter/retweet/<tweet_id>', methods=['POST'])
async def retweet(tweet_id):
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
        if not api:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Twitter client. Please connect your Twitter account."}}), 401

        tweet = await twitter_service.retweet(api, tweet_id)
        return jsonify({"ok": True, "data": tweet})
    except Exception as e:
        logger.error(f"Error retweeting tweet {tweet_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "RETWEET_FAILED", "message": str(e)}}), 500

@twitter_bp.route('/api/twitter/like/<tweet_id>', methods=['POST'])
async def like_tweet(tweet_id):
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
        if not api:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Twitter client. Please connect your Twitter account."}}), 401

        tweet = await twitter_service.like_tweet(api, tweet_id)
        return jsonify({"ok": True, "data": tweet})
    except Exception as e:
        logger.error(f"Error liking tweet {tweet_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIKE_FAILED", "message": str(e)}}), 500

@twitter_bp.route('/api/twitter/tweet/<tweet_id>', methods=['GET'])
async def get_tweet(tweet_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        api = await twitter_service.get_twitter_api(user_id, db_conn_pool)
        if not api:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Twitter client. Please connect your Twitter account."}}), 401

        tweet = await twitter_service.get_tweet(api, tweet_id)
        return jsonify({"ok": True, "data": tweet})
    except Exception as e:
        logger.error(f"Error getting tweet {tweet_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TWEET_FETCH_FAILED", "message": str(e)}}), 500
