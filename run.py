from app import create_app

# إنشاء التطبيق
app = create_app()

if __name__ == '__main__':
    # تشغيل السيرفر
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=5000
    )