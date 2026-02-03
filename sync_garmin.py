import os
import json
import base64
import zipfile
import io
import garth
from garminconnect import Garmin
from google.oauth2.service_account import Credentials
import gspread

def main():
    print("Starting ALL-Activity Garmin sync...")
    
    # Credentials laden
    garmin_email = os.environ.get('GARMIN_EMAIL')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')
    session_base64 = os.environ.get('GARMIN_SESSION_BASE64')
    
    # --- GARMIN LOGIN ---
    garmin = None
    if session_base64:
        try:
            decoded_data = base64.b64decode(session_base64)
            with zipfile.ZipFile(io.BytesIO(decoded_data)) as z:
                z.extractall('session_data')
            garth.resume('session_data')
            garmin = Garmin()
            garmin.garth = garth.client
            print("✅ Login via Session successful")
        except Exception as e:
            print(f"⚠️ Session failed: {e}")

    if not garmin or not garmin.garth.profile:
        garmin = Garmin(garmin_email, garmin_password)
        garmin.login()

    # Aktivitäten holen (letzte 30, um sicherzugehen)
    activities = garmin.get_activities(0, 30)
    
    # --- GOOGLE SHEETS ---
    creds_dict = json.loads(google_creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).sheet1
    all_rows = sheet.get_all_values()
    
    # Erweiterte Kopfzeilen basierend auf deinem CSV-Wunsch
    headers = [
        "Date", "Activity Type", "Title", "Distance (km)", "Calories", "Duration (min)", 
        "Avg HR", "Max HR", "Aerobic TE", "Avg Cadence", "Max Cadence", 
        "Avg Speed (km/h)", "Max Speed (km/h)", "Total Ascent", "Total Descent", 
        "Avg Stride Length", "Avg GCT Balance", "Avg GAP", "Avg Power", "Max Power", 
        "Training Stress Score", "Steps", "Total Reps", "Total Poses", 
        "Body Battery Drain", "Min Temp", "Max Temp", "Avg Resp", "Min Resp", "Max Resp",
        "Moving Time", "Elapsed Time", "Min Elevation", "Max Elevation"
    ]

    if not all_rows or all_rows[0][0] != "Date":
        sheet.insert_row(headers, 1)
        all_rows = sheet.get_all_values()
    
    existing_dates = {row[0] for row in all_rows if row}

    new_entries = 0
    # Alle Aktivitäten verarbeiten (Kein Filter mehr auf 'running'!)
    for act in reversed(activities):
        full_start_time = act.get('startTimeLocal', '')
        if full_start_time in existing_dates:
            continue

        # Mapping der Garmin API Werte (viele Felder sind optional je nach Sportart)
        row = [
            full_start_time,
            act.get('activityType', {}).get('typeKey', ''),
            act.get('activityName', ''),
            round(act.get('distance', 0) / 1000, 2),
            act.get('calories', 0),
            round(act.get('duration', 0) / 60, 2),
            act.get('averageHR', 0),
            act.get('maxHR', 0),
            act.get('aerobicTrainingEffect', 0),
            act.get('averageRunningCadenceInStepsPerMinute', act.get('averageBikeCadence', 0)), # Kombiniert Run/Bike
            act.get('maxRunningCadenceInStepsPerMinute', act.get('maxBikeCadence', 0)),
            round(act.get('averageSpeed', 0) * 3.6, 2),
            round(act.get('maxSpeed', 0) * 3.6, 2),
            round(act.get('elevationGain', 0), 1),
            round(act.get('elevationLoss', 0), 1),
            act.get('avgStrideLength', 0),
            act.get('avgGroundContactBalance', 0),
            act.get('avgGradeAdjustedSpeed', 0),
            act.get('avgPower', 0),
            act.get('maxPower', 0),
            act.get('trainingStressScore', 0),
            act.get('steps', 0),
            act.get('totalReps', 0),
            act.get('totalPoses', 0),
            act.get('bodyBatteryDrainValue', 0),
            act.get('minTemperature', 0),
            act.get('maxTemperature', 0),
            act.get('averageRespirationRate', 0),
            act.get('minRespirationRate', 0),
            act.get('maxRespirationRate', 0),
            round(act.get('movingDuration', 0) / 60, 2),
            round(act.get('elapsedDuration', 0) / 60, 2),
            round(act.get('minElevation', 0), 1),
            round(act.get('maxElevation', 0), 1)
        ]
        
        sheet.append_row(row)
        print(f"✅ Added {act.get('activityType', {}).get('typeKey')}: {full_start_time}")
        new_entries += 1

    print(f"Done! {new_entries} activities added.")

if __name__ == "__main__":
    main()
