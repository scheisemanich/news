#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube News Playlist Updater

Dieses Skript aktualisiert eine bestehende YouTube-Playlist mit den neuesten Nachrichtenvideos:
1. Liest die Playlist-ID aus der Konfigurationsdatei
2. Löscht den Inhalt der Playlist (behält die Playlist selbst)
3. Liest die Videos aus der latest_news.json Datei
4. Sortiert sie nach Erscheinungsdatum (neueste zuerst)
5. Fügt die Videos in dieser Reihenfolge zur Playlist hinzu
"""

import os
import json
import argparse
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

def update_news_playlist(json_file="output/latest_news.json", 
                         credentials_file="config/client_secret.json",
                         token_file="config/token.json", 
                         playlist_id_file="config/playlist_id.txt"):
    """
    Aktualisiert eine bestehende YouTube-Playlist mit den neuesten Nachrichtenvideos.
    
    Args:
        json_file (str): Pfad zur JSON-Datei mit den Videoinformationen
        credentials_file (str): Pfad zur OAuth 2.0 Client-Credentials-Datei
        token_file (str): Pfad zur Token-Datei
        playlist_id_file (str): Pfad zur Datei mit der Playlist-ID
    
    Returns:
        bool: True bei Erfolg, False bei Fehler
    """
    print(f"Starte Playlist-Aktualisierung mit Daten aus {json_file}...")
    
    # 1. Playlist-ID aus Datei lesen
    try:
        with open(playlist_id_file, 'r') as f:
            playlist_id = f.read().strip()
        
        if not playlist_id:
            print(f"Fehler: Keine Playlist-ID in {playlist_id_file} gefunden.")
            return False
            
        print(f"Gefundene Playlist-ID: {playlist_id}")
    except FileNotFoundError:
        print(f"Fehler: Playlist-ID-Datei {playlist_id_file} nicht gefunden.")
        return False
    
    # 2. Videodaten aus JSON-Datei laden
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            videos = json.load(f)
            
        if not videos:
            print("Keine Videos in der JSON-Datei gefunden.")
            return False
            
        print(f"{len(videos)} Videos aus JSON-Datei geladen.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Fehler beim Laden der JSON-Datei: {e}")
        return False
    
    # 3. Nach YouTube API authentifizieren
    try:
        if not os.path.exists(token_file):
            print(f"Fehler: Token-Datei {token_file} nicht gefunden.")
            return False
            
        with open(token_file, 'r') as f:
            token_data = json.load(f)
            
        creds = Credentials.from_authorized_user_info(token_data)
        
        if not creds or not creds.valid:
            print("Fehler: Ungültige oder abgelaufene Anmeldedaten.")
            return False
            
        youtube = build('youtube', 'v3', credentials=creds)
        print("Erfolgreich bei YouTube API authentifiziert.")
    except Exception as e:
        print(f"Fehler bei der Authentifizierung: {e}")
        return False
    
    # 4. Vorhandene Videos aus der Playlist löschen
    try:
        items_deleted = 0
        request = youtube.playlistItems().list(
            part="id",
            playlistId=playlist_id,
            maxResults=50
        )
        
        while request:
            response = request.execute()
            
            # Jeden Eintrag löschen
            for item in response.get("items", []):
                youtube.playlistItems().delete(
                    id=item["id"]
                ).execute()
                items_deleted += 1
            
            # Nächste Seite mit Ergebnissen
            request = youtube.playlistItems().list_next(request, response)
        
        print(f"{items_deleted} Videos aus der Playlist entfernt.")
    except HttpError as e:
        print(f"Fehler beim Löschen der Playlist-Einträge: {e}")
        return False
    
    # 5. Videos nach Erscheinungsdatum sortieren (neueste zuerst)
    try:
        # Umwandeln der ISO-8601 Zeitangaben in datetime-Objekte für die Sortierung
        for video in videos:
            if 'published_at' in video:
                # Standardisierte ISO-8601-Zeitangabe in datetime-Objekt umwandeln
                published_at = video['published_at'].replace('Z', '+00:00')
                video['_published_datetime'] = datetime.fromisoformat(published_at)
            else:
                # Fallback, wenn kein Veröffentlichungsdatum vorhanden ist
                video['_published_datetime'] = datetime.min
        
        # Nach Datum sortieren (neueste zuerst)
        videos.sort(key=lambda x: x['_published_datetime'], reverse=True)
        
        print("Videos nach Erscheinungsdatum sortiert (neueste zuerst).")
    except Exception as e:
        print(f"Fehler beim Sortieren der Videos: {e}")
        # Fortfahren, auch wenn die Sortierung fehlschlägt
    
    # 6. Videos zur Playlist hinzufügen
    try:
        videos_added = 0
        
        for video in videos:
            video_id = video['id']
            
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        },
                        # Position exakt setzen, damit die Reihenfolge stimmt
                        "position": videos_added
                    }
                }
            ).execute()
            
            videos_added += 1
            
            # Optionale Ausgabe für jedes hinzugefügte Video
            print(f"Video hinzugefügt: {video.get('title', video_id)} (veröffentlicht am {video.get('published_at', 'unbekannt')})")
        
        print(f"Insgesamt {videos_added} Videos zur Playlist hinzugefügt.")
    except HttpError as e:
        print(f"Fehler beim Hinzufügen von Videos zur Playlist: {e}")
        # Teilerfolg, wenn einige Videos hinzugefügt wurden
        if videos_added > 0:
            print(f"Es wurden {videos_added} Videos erfolgreich hinzugefügt, bevor der Fehler auftrat.")
            return True
        return False
    
    # 7. Playlist-Informationen ausgeben
    try:
        playlist_response = youtube.playlists().list(
            part="snippet,contentDetails",
            id=playlist_id
        ).execute()
        
        if playlist_response.get("items"):
            playlist = playlist_response["items"][0]
            print("\nPlaylist-Informationen:")
            print(f"Titel: {playlist['snippet']['title']}")
            print(f"Anzahl Videos: {playlist['contentDetails']['itemCount']}")
            print(f"URL: https://www.youtube.com/playlist?list={playlist_id}")
    except HttpError as e:
        print(f"Fehler beim Abrufen der Playlist-Informationen: {e}")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube News Playlist Updater")
    parser.add_argument("--json-file", default="output/latest_news.json", 
                       help="Pfad zur JSON-Datei mit den Videos")
    parser.add_argument("--credentials", default="config/client_secret.json", 
                       help="Pfad zur OAuth 2.0 Client-Credentials-Datei")
    parser.add_argument("--token", default="config/token.json",
                       help="Pfad zur Token-Datei")
    parser.add_argument("--playlist-id-file", default="config/playlist_id.txt",
                       help="Pfad zur Datei mit der Playlist-ID")
    parser.add_argument("--verbose", action="store_true",
                       help="Ausführliche Ausgabe")
    
    args = parser.parse_args()
    
    success = update_news_playlist(
        json_file=args.json_file,
        credentials_file=args.credentials,
        token_file=args.token,
        playlist_id_file=args.playlist_id_file
    )
    
    if success:
        print("Playlist-Aktualisierung erfolgreich abgeschlossen.")
        exit(0)
    else:
        print("Playlist-Aktualisierung fehlgeschlagen.")
        exit(1)
