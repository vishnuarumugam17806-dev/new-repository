"""
DB VITHRA — System Analytics & Platform Management Dashboard Blueprint
Computes multi-database statistics across SQL Server, MySQL, Oracle, MongoDB, and Excel.
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

    # Multi-database breakdown
    sqlserver_count = SharedDatabase.query.filter_by(database_type='sqlserver').count()
    mysql_count     = SharedDatabase.query.filter_by(database_type='mysql').count()
    oracle_count    = SharedDatabase.query.filter_by(database_type='oracle').count()
    mongodb_count   = SharedDatabase.query.filter_by(database_type='mongodb').count()
    excel_count     = SharedDatabase.query.filter_by(database_type='excel').count()

    db_types_breakdown = [
        ('SQL Server', sqlserver_count, 'fa-database', 'purple'),
        ('MySQL Engine', mysql_count, 'fa-server', 'cyan'),
        ('Oracle DB', oracle_count, 'fa-building-columns', 'pink'),
        ('MongoDB (NoSQL)', mongodb_count, 'fa-leaf', 'green'),
        ('Excel Workbooks', excel_count, 'fa-file-excel', 'amber')
    ]

    recent_schemas = SharedDatabase.query.order_by(SharedDatabase.created_at.desc()).limit(10).all()
    top_schemas    = SharedDatabase.query.order_by(SharedDatabase.views_count.desc()).limit(5).all()

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

    return render_template('analytics.html',
        total_schemas=total_schemas,
        total_downloads=total_downloads,
        total_views=total_views,
        sqlserver_count=sqlserver_count,
        mysql_count=mysql_count,
        oracle_count=oracle_count,
        mongodb_count=mongodb_count,
        excel_count=excel_count,
        db_types_breakdown=db_types_breakdown,
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

    return jsonify({
        'total_schemas':   SharedDatabase.query.count(),
        'total_downloads': DownloadLog.query.count(),
        'sqlserver_count': SharedDatabase.query.filter_by(database_type='sqlserver').count(),
        'mysql_count':     SharedDatabase.query.filter_by(database_type='mysql').count(),
        'oracle_count':    SharedDatabase.query.filter_by(database_type='oracle').count(),
        'mongodb_count':   SharedDatabase.query.filter_by(database_type='mongodb').count(),
        'excel_count':     SharedDatabase.query.filter_by(database_type='excel').count(),
        'trend':           trend,
    })
