from app import create_app

# إنشاء التطبيق
app = create_app()


@app.cli.command('cleanup-clips')
def cleanup_clips():
    """Delete expired game clips (file + DB). Run via cron every hour."""
    import os
    from datetime import datetime
    from app.models.main import GameClip
    from app import db

    clips_dir = app.config.get('CLIPS_FOLDER', '')
    expired = GameClip.query.filter(GameClip.expires_at < datetime.utcnow()).all()
    count = 0
    for c in expired:
        if c.filename:
            path = os.path.join(clips_dir, c.filename)
            try:
                os.remove(path)
            except OSError:
                pass
        db.session.delete(c)
        count += 1
    if count:
        db.session.commit()
    print(f'[cleanup-clips] Deleted {count} expired clip(s).')


if __name__ == '__main__':
    # تشغيل السيرفر
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=5000
    )