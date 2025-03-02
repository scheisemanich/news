#!/bin/bash
# Script zum Aktualisieren der Pfade und Pushen der Änderungen ins Remote-Repository

# Korrekter Basispfad (ohne /ai/)
NEW_BASE_PATH="/Users/brunowinter/Documents/news"
OLD_BASE_PATH="/Users/brunowinter/Documents/ai/news"

echo "1. Aktualisiere Pfade in den Dateien..."

# Aktualisiere hourly_news_playlist.sh
if grep -q "$OLD_BASE_PATH" hourly_news_playlist.sh; then
  echo "Aktualisiere hourly_news_playlist.sh..."
  sed -i '' "s|$OLD_BASE_PATH|$NEW_BASE_PATH|g" hourly_news_playlist.sh
  echo "✅ Pfad in hourly_news_playlist.sh aktualisiert"
else
  echo "Kein Pfad zum Aktualisieren in hourly_news_playlist.sh gefunden"
fi

# Aktualisiere die plist-Datei im config-Verzeichnis
if [ -f "../config/com.brunowinter.youtubenews.plist" ] && grep -q "$OLD_BASE_PATH" "../config/com.brunowinter.youtubenews.plist"; then
  echo "Aktualisiere ../config/com.brunowinter.youtubenews.plist..."
  sed -i '' "s|$OLD_BASE_PATH|$NEW_BASE_PATH|g" "../config/com.brunowinter.youtubenews.plist"
  echo "✅ Pfad in ../config/com.brunowinter.youtubenews.plist aktualisiert"
else
  echo "Kein Pfad zum Aktualisieren in ../config/com.brunowinter.youtubenews.plist gefunden"
fi

# Suche nach anderen Dateien mit dem alten Pfad
echo "Suche nach weiteren Dateien mit dem alten Pfad..."
cd ..
grep -r --include="*.py" --include="*.sh" --include="*.json" --include="*.plist" "$OLD_BASE_PATH" .
echo "Falls weitere Dateien gefunden wurden, aktualisiere diese manuell."

echo "2. Mache Skripte ausführbar..."
chmod +x scripts/*.sh
chmod +x scripts/*.py

echo "3. Führe lokalen Test durch..."
./scripts/hourly_news_playlist.sh

echo "4. Füge Änderungen zum Git-Stage hinzu..."
git add scripts/hourly_news_playlist.sh
git add config/com.brunowinter.youtubenews.plist
git add scripts/*.sh scripts/*.py

echo "5. Erstelle Commit..."
git commit -m "Update Pfade von /ai/news zu /news und mache Skripte ausführbar"

echo "6. Pushe Änderungen zum Remote-Repository..."
git push

echo "Fertig! Änderungen wurden durchgeführt und zum Remote-Repository gepusht."
