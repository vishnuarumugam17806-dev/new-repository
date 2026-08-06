"""
SMART DB — Marketplace Blueprint
Handles schema marketplace, comments, likes, ratings, and industry templates.
"""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from sqlalchemy import or_
from models import db, SharedDatabase, Comment, Rating, IndustryTemplate
from utils import _track, translate_sql

marketplace_bp = Blueprint('marketplace', __name__)

@marketplace_bp.route('/store')
def store():
    search_query = request.args.get('q', '').strip()
    industry     = request.args.get('industry', '').strip()
    sort_by      = request.args.get('sort', 'newest')

    query = SharedDatabase.query

    if search_query:
        query = query.filter(or_(
            SharedDatabase.project_name.ilike(f'%{search_query}%'),
            SharedDatabase.requirements.ilike(f'%{search_query}%'),
            SharedDatabase.tags.ilike(f'%{search_query}%'),
            SharedDatabase.industry.ilike(f'%{search_query}%'),
        ))
    if industry:
        query = query.filter(SharedDatabase.industry.ilike(f'%{industry}%'))

    if sort_by == 'popular':
        query = query.order_by(SharedDatabase.views_count.desc())
    elif sort_by == 'downloads':
        query = query.order_by(SharedDatabase.downloads_count.desc())
    elif sort_by == 'likes':
        query = query.order_by(SharedDatabase.likes_count.desc())
    else:
        query = query.order_by(SharedDatabase.created_at.desc())

    databases   = query.all()
    industries  = db.session.query(SharedDatabase.industry).distinct().all()
    industries  = [i[0] for i in industries if i[0]]

    total_count = SharedDatabase.query.count()
    ai_count    = SharedDatabase.query.filter_by(ai_generated=True).count()

    return render_template('store.html',
        databases=databases,
        search_query=search_query,
        industry=industry,
        sort_by=sort_by,
        industries=industries,
        total_count=total_count,
        ai_count=ai_count,
    )


@marketplace_bp.route('/templates')
def templates_page():
    category    = request.args.get('category', '').strip()
    templates_q = IndustryTemplate.query
    if category:
        templates_q = templates_q.filter_by(category=category)
    templates   = templates_q.order_by(IndustryTemplate.is_featured.desc(), IndustryTemplate.downloads.desc()).all()
    categories  = db.session.query(IndustryTemplate.category).distinct().all()
    categories  = [c[0] for c in categories if c[0]]
    return render_template('templates_page.html', templates=templates,
                           categories=categories, active_category=category)


@marketplace_bp.route('/templates/<int:tmpl_id>/use')
def use_template(tmpl_id):
    tmpl = db.session.get(IndustryTemplate, tmpl_id)
    if tmpl is None:
        from flask import abort
        abort(404)
    clean_name = re.sub(r'[^A-Za-z0-9_]', '', tmpl.name.title().replace(' ', ''))
    return redirect(url_for('generator.create_database') + f'?use_template={tmpl_id}&project_name={clean_name}')


@marketplace_bp.route('/schema/<int:db_id>/like', methods=['POST'])
def like_schema(db_id):
    schema = SharedDatabase.query.get_or_404(db_id)
    schema.likes_count = (schema.likes_count or 0) + 1
    db.session.commit()
    return jsonify({'likes': schema.likes_count})


@marketplace_bp.route('/schema/<int:db_id>/comment', methods=['POST'])
def add_comment(db_id):
    schema      = SharedDatabase.query.get_or_404(db_id)
    content     = request.form.get('content', '').strip()
    
    if current_user.is_authenticated:
        author_name = current_user.username
        user_id = current_user.id
    else:
        author_name = request.form.get('author_name', 'Anonymous').strip() or 'Anonymous'
        user_id = None

    if content:
        c = Comment(schema_id=db_id, user_id=user_id, author_name=author_name, content=content)
        db.session.add(c)
        db.session.commit()
        flash('Comment added!', 'success')
    return redirect(url_for('generator.database_details', db_id=db_id) + '#comments')


@marketplace_bp.route('/schema/<int:db_id>/rate', methods=['POST'])
def rate_schema(db_id):
    score = request.form.get('score', type=int)
    user_id = current_user.id if current_user.is_authenticated else None
    
    if score and 1 <= score <= 5:
        # Check if user already rated if logged in
        if user_id:
            existing = Rating.query.filter_by(schema_id=db_id, user_id=user_id).first()
            if existing:
                existing.score = score
                db.session.commit()
                flash(f'Your rating has been updated to {score}/5 stars.', 'success')
                return redirect(url_for('generator.database_details', db_id=db_id))

        r = Rating(schema_id=db_id, user_id=user_id, score=score)
        db.session.add(r)
        db.session.commit()
        flash(f'Thanks for rating! You gave {score}/5 stars.', 'success')
    return redirect(url_for('generator.database_details', db_id=db_id))
