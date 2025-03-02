#!/bin/bash

# Pfad zum Projektverzeichnis - bei GitHub Actions ist das das aktuelle Verzeichnis
PROJECT_DIR="."
# Pfad zur Konfigurationsdatei
CONFIG_FILE="$PROJECT_DIR/config/config.json"
# Pfad zur JSON-Ausgabedatei
JSON_FILE="$PROJECT_DIR/output/latest_news.json"
# Pfad zur OAuth-Credentials-Datei
CREDENTIALS_FILE="$PROJECT_DIR/config/client_secret.json"

# Playlist-ID speichern
PLAYLIST_ID_FILE="$PROJECT_DIR/config/playlist_id.txt"

# Logdateien
LOG_FILE="$PROJECT_DIR/logs/update_log.txt"
SUMMARY_LOG="$PROJECT_DIR/logs/update_summary.txt"

# Datum und Uhrzeit für Log-Ausgabe
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Stelle sicher, dass die Verzeichnisse existieren
mkdir -p "$PROJECT_DIR/config" "$PROJECT_DIR/output" "$PROJECT_DIR/logs"

# Führe eine Sicherung der vorherigen JSON-Datei durch, falls vorhanden
PREVIOUS_VIDEOS=0
PREVIOUS_IDS=()
if [ -f "$JSON_FILE" ]; then
    cp "$JSON_FILE" "$PROJECT_DIR/output/previous_news.json"
    # Zähle Videos in der vorherigen JSON-Datei
    PREVIOUS_VIDEOS=$(grep -o "\"id\":" "$JSON_FILE" | wc -l)
    # Extrahiere Video-IDs aus der vorherigen JSON-Datei
    PREVIOUS_IDS=($(grep -o "\"id\":\s*\"[^\"]*\"" "$JSON_FILE" | cut -d'"' -f4))
fi

echo "--------------------------------" >> "$LOG_FILE"
echo "Starte Update am $TIMESTAMP" >> "$LOG_FILE"
echo "--------------------------------" >> "$LOG_FILE"

# Aktualisiere die News-Feeds
# Wichtig: Hier setzen wir --days-back=2 für 48 Stunden
echo "Sammle aktuelle News-Videos der letzten 48 Stunden..." >> "$LOG_FILE"
python "$PROJECT_DIR/scripts/youtube_news_aggregator.py" --load-config "$CONFIG_FILE" --days-back 2 --now --output-dir "$PROJECT_DIR/output/" >> "$LOG_FILE" 2>&1

# Prüfe, ob die JSON-Datei erstellt wurde
if [ ! -f "$JSON_FILE" ]; then
    echo "Fehler: JSON-Datei wurde nicht gefunden. Der News Aggregator ist möglicherweise fehlgeschlagen." >> "$LOG_FILE"
    echo "[$TIMESTAMP] FEHLER: JSON-Datei nicht gefunden" >> "$SUMMARY_LOG"
    exit 1
fi

# Zähle die Anzahl der gefundenen Videos in der neuen JSON-Datei
NEW_VIDEOS=$(grep -o "\"id\":" "$JSON_FILE" | wc -l)
# Extrahiere Video-IDs aus der neuen JSON-Datei
NEW_IDS=($(grep -o "\"id\":\s*\"[^\"]*\"" "$JSON_FILE" | cut -d'"' -f4))

# Berechne hinzugefügte und entfernte Videos
ADDED_IDS=()
for id in "${NEW_IDS[@]}"; do
    if [[ ! " ${PREVIOUS_IDS[*]} " =~ " ${id} " ]]; then
        ADDED_IDS+=("$id")
    fi
done

REMOVED_IDS=()
for id in "${PREVIOUS_IDS[@]}"; do
    if [[ ! " ${NEW_IDS[*]} " =~ " ${id} " ]]; then
        REMOVED_IDS+=("$id")
    fi
done

ADDED_COUNT=${#ADDED_IDS[@]}
REMOVED_COUNT=${#REMOVED_IDS[@]}

echo "Aktuelle Anzahl Videos: $NEW_VIDEOS" >> "$LOG_FILE"
echo "Hinzugefügte Videos: $ADDED_COUNT" >> "$LOG_FILE"
echo "Entfernte Videos: $REMOVED_COUNT" >> "$LOG_FILE"

# Bei größeren Änderungen, zeige Details
if [ "$ADDED_COUNT" -gt 0 ]; then
    echo "Hinzugefügte Video-IDs:" >> "$LOG_FILE"
    for id in "${ADDED_IDS[@]}"; do
        TITLE=$(grep -A 3 "\"id\": \"$id\"" "$JSON_FILE" | grep "\"title\":" | head -1 | cut -d'"' -f4)
        echo "  - $id: $TITLE" >> "$LOG_FILE"
    done
fi

# Aktualisiere die YouTube-Playlist
echo "Aktualisiere YouTube-Playlist..." >> "$LOG_FILE"

# Prüfe, ob bereits eine Playlist-ID gespeichert wurde
if [ -f "$PLAYLIST_ID_FILE" ]; then
    # Lese die Playlist-ID aus der Datei
    PLAYLIST_ID=$(cat "$PLAYLIST_ID_FILE")
    echo "Aktualisiere bestehende Playlist ($PLAYLIST_ID)..." >> "$LOG_FILE"
    python "$PROJECT_DIR/scripts/youtube_playlist_creator.py" --json-file "$JSON_FILE" --credentials "$CREDENTIALS_FILE" --playlist-id "$PLAYLIST_ID" >> "$LOG_FILE" 2>&1
    UPDATE_STATUS=$?
    
    # Prüfe, ob das Update erfolgreich war
    if [ $UPDATE_STATUS -eq 0 ]; then
        UPDATE_MSG="ERFOLG"
    else
        UPDATE_MSG="FEHLER (Code: $UPDATE_STATUS)"
    fi
else
    # Erstelle eine neue Playlist und speichere die ID
    echo "Erstelle neue Playlist..." >> "$LOG_FILE"
    OUTPUT=$(python "$PROJECT_DIR/scripts/youtube_playlist_creator.py" --json-file "$JSON_FILE" --credentials "$CREDENTIALS_FILE" --title "Meine News (48h)" --privacy "private")
    UPDATE_STATUS=$?
    
    if [ $UPDATE_STATUS -eq 0 ]; then
        UPDATE_MSG="NEUE PLAYLIST ERSTELLT"
        
        # Extrahiere die Playlist-ID aus der Ausgabe
        PLAYLIST_ID=$(echo "$OUTPUT" | grep "Created playlist:" | sed -E 's/.*\(ID: ([^)]+)\).*/\1/')
        
        if [ -n "$PLAYLIST_ID" ]; then
            echo "Neue Playlist-ID: $PLAYLIST_ID" >> "$LOG_FILE"
            echo "$PLAYLIST_ID" > "$PLAYLIST_ID_FILE"
            echo "Playlist-ID wurde gespeichert in: $PLAYLIST_ID_FILE" >> "$LOG_FILE"
        else
            echo "Warnung: Konnte keine Playlist-ID aus der Ausgabe extrahieren." >> "$LOG_FILE"
            echo "Bitte überprüfe die Ausgabe und aktualisiere die Playlist-ID manuell." >> "$LOG_FILE"
            echo "$OUTPUT" >> "$LOG_FILE"
            UPDATE_MSG="FEHLER: Playlist-ID nicht gefunden"
        fi
    else
        UPDATE_MSG="FEHLER (Code: $UPDATE_STATUS)"
    fi
fi

# Schreibe eine Zusammenfassung in die summary log Datei
echo "[$TIMESTAMP] $UPDATE_MSG - Aktuelle Videos: $NEW_VIDEOS, Hinzugefügt: $ADDED_COUNT, Entfernt: $REMOVED_COUNT" >> "$SUMMARY_LOG"

echo "--------------------------------" >> "$LOG_FILE"
echo "Update abgeschlossen am $(date "+%Y-%m-%d %H:%M:%S")" >> "$LOG_FILE"
echo "--------------------------------" >> "$LOG_FILE"
