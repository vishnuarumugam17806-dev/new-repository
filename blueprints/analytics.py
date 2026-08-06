"""
SMART DB — Analytics Blueprint
Handles tracking event statistics, trend analysis and reporting metrics.
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify
from sqlalchemy import func
from models import db, SharedDatabase, DownloadLog

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics')
def analytics():
    total_schemas    = SharedDatabase.query.count()
    total_downloads  = DownloadLog.query.count()
    total_views      = db.session.query(func.sum(SharedDatabase.views_count)).scalar() or 0
    ai_schemas       = SharedDatabase.query.filter_by(ai_generated=True).count()
    industries_rows = db.session.query(SharedDatabase.industry, func.count(SharedDatabase.id)).group_by(SharedDatabase.industry).all()
    industries      = [(r[0] or 'General', r[1]) for r in industries_rows]
    recent_schemas   = SharedDatabase.query.order_by(SharedDatabase.created_at.desc()).limit(10).all()
    top_schemas      = SharedDatabase.query.order_by(SharedDatabase.views_count.desc()).limit(5).all()

    # Daily generation trend (last 7 days)
    today   = datetime.utcnow().date()
    trend   = []
    for i in range(6, -1, -1):
        day       = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_next  = day_start + timedelta(days=1)
        count     = SharedDatabase.query.filter(
            SharedDatabase.created_at >= day_start,
            SharedDatabase.created_at < day_next
        ).count()
        trend.append({'date': day.strftime('%b %d'), 'count': count})

    return render_template('analytics.html',
        total_schemas=total_schemas,
        total_downloads=total_downloads,
        total_views=total_views,
        ai_schemas=ai_schemas,
        industries=industries,
        recent_schemas=recent_schemas,
        top_schemas=top_schemas,
        trend=trend,
    )


@analytics_bp.route('/api/analytics/stats')
def api_analytics_stats():
    today = datetime.utcnow().date()
    trend = []
    for i in range(6, -1, -1):
        day       = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_next  = day_start + timedelta(days=1)
        count     = SharedDatabase.query.filter(
            SharedDatabase.created_at >= day_start,
            SharedDatabase.created_at < day_next
        ).count()
        trend.append({'date': day.strftime('%b %d'), 'count': count})

    industries = db.session.query(SharedDatabase.industry, func.count(SharedDatabase.id)).group_by(SharedDatabase.industry).all()
    return jsonify({
        'total_schemas':   SharedDatabase.query.count(),
        'total_downloads': DownloadLog.query.count(),
        'ai_schemas':      SharedDatabase.query.filter_by(ai_generated=True).count(),
        'trend':           trend,
        'industries':      [{'name': i[0] or 'General', 'count': i[1]} for i in industries],
    })
