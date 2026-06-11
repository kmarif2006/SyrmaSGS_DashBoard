from backend.app import app


if __name__ == "__main__":
    import os

    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    print("Syrma Procurement Analytics -- Backend starting on http://localhost:5000")
    app.run(debug=debug_mode, port=5000, host="0.0.0.0")