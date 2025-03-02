#!/bin/bash

CONFIG_FILE="$PROJECT_DIR/config/config.json"
JSON_FILE="$PROJECT_DIR/output/latest_news.json"
CREDENTIALS_FILE="$PROJECT_DIR/config/client_secret.json"
PLAYLIST_ID_FILE="$PROJECT_DIR/config/playlist_id.txt"

# Datum für Log-Ausgabe
echo "--------------------------------"
echo "Starte Update am $(date)"
echo "--------------------------------"

# Wechsle ins Projektverzeichnis
cd "$PROJECT_DIR" || { echo "Fehler: Verzeichnis nicht gefunden"; exit 1; }

# Aktiviere die Python-Umgebung, falls vorhanden
# Entferne die Kommentarzeichen, wenn du eine virtuelle Umgebung verwendest
# source venv/bin/activate

# Aktualisiere die News-Feeds
echo "Sammle aktuelle News-Videos..."
python youtube_news_aggregator.py --load-config "$CONFIG_FILE" --now

# Prüfe, ob die JSON-Datei erstellt wurde
if [ ! -f "$JSON_FILE" ]; then
    echo "Fehler: JSON-Datei wurde nicht gefunden. Der News Aggregator ist möglicherweise fehlgeschlagen."
    exit 1
fi

# Warte kurz, um sicherzustellen, dass die JSON-Datei vollständig geschrieben wurde
sleep 5

# Aktualisiere die YouTube-Playlist
echo "Aktualisiere YouTube-Playlist..."

# Prüfe, ob bereits eine Playlist-ID gespeichert wurde
if [ -f "$PLAYLIST_ID_FILE" ]; then
    # Lese die Playlist-ID aus der Datei
    PLAYLIST_ID=$(cat "$PLAYLIST_ID_FILE")
    echo "Aktualisiere bestehende Playlist ($PLAYLIST_ID)..."
    python youtube_playlist_creator.py --json-file "$JSON_FILE" --credentials "$CREDENTIALS_FILE" --playlist-id "$PLAYLIST_ID"
else
    # Erstelle eine neue Playlist und speichere die ID
    echo "Erstelle neue Playlist..."
    OUTPUT=$(python youtube_playlist_creator.py --json-file "$JSON_FILE" --credentials "$CREDENTIALS_FILE" --title "Meine News" --privacy "private")
    
    # Extrahiere die Playlist-ID aus der Ausgabe
    # Suche nach Zeilen wie "Created playlist: Meine News (ID: PL1234567890ABCDEF)"
    PLAYLIST_ID=$(echo "$OUTPUT" | grep "Created playlist:" | sed -E 's/.*\(ID: ([^)]+)\).*/\1/')
    
    if [ -n "$PLAYLIST_ID" ]; then
        echo "Neue Playlist-ID: $PLAYLIST_ID"
        echo "$PLAYLIST_ID" > "$PLAYLIST_ID_FILE"
        echo "Playlist-ID wurde gespeichert in: $PLAYLIST_ID_FILE"
    else
        echo "Warnung: Konnte keine Playlist-ID aus der Ausgabe extrahieren."
        echo "Bitte überprüfe die Ausgabe und aktualisiere die Playlist-ID manuell."
        echo "$OUTPUT"
    fi
fi

echo "--------------------------------"
echo "Update abgeschlossen am $(date)"
echo "--------------------------------"