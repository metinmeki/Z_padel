from app import create_app

# إنشاء التطبيق
app = create_app()

if __name__ == '__main__':
    # تشغيل السيرفر
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000
    )