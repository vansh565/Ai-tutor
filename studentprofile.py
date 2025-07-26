import pandas as pd
import os

def fetch_student_profile(student_id):
    try:
        if not os.path.exists("student_profiles.csv") or os.stat("student_profiles.csv").st_size == 0:
            print("CSV file missing or empty. Creating dummy file...")
            # Dummy data
            df = pd.DataFrame([
                {"student_id": "student_123", "name": "vansh", "weak_topics": "Maths;Graphs", "strong_topics": "DP;Trees"},
                {"student_id": "student_456", "name": "piyush", "weak_topics": "OS;DBMS", "strong_topics": "CN;Java"},
            ])
            df.to_csv("student_profiles.csv", index=False)

        df = pd.read_csv("student_profiles.csv")
        student = df[df["student_id"] == student_id]
        if student.empty:
            print(f"No profile found for student_id: {student_id}")
            return None
        return student.iloc[0].to_dict()
    except Exception as e:
        print(f"Error fetching student profile: {e}")
        return None