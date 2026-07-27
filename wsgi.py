"""WSGI entry point. `flask run` (with FLASK_APP=wsgi.py) uses `app`.

Run `python seed.py` first to create the database and demo data.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # `python wsgi.py` also works for a quick local run.
    app.run(debug=True)
