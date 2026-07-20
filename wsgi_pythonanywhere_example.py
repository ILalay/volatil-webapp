# ============================================================
# Diese Datei ist NUR eine Vorlage.
#
# Auf PythonAnywhere findest du unter "Web" -> deine Domain ->
# "Code" einen Link zur WSGI-Konfigurationsdatei
# (z. B. /var/www/deinname_pythonanywhere_com_wsgi.py).
# Öffne diese Datei dort und ersetze ihren Inhalt durch das
# Folgende (Pfad und Projektname anpassen).
# ============================================================

import sys

# Pfad zu dem Ordner, in dem app.py liegt
project_home = "/home/DEINBENUTZERNAME/volatil_webapp"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app as application  # noqa: E402
