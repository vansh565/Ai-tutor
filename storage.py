import pandas as pd
import os

def save_notes(student_id, subject, topic, notes):
    filename = "student_notes.csv"

    new_data = {
        "student_id": student_id,
        "subject": subject,
        "topic": topic,
        "notes": notes
    }

    if os.path.exists(filename):
        df = pd.read_csv(filename)
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    else:
        df = pd.DataFrame([new_data])

    df.to_csv(filename, index=False)
    print("✅ Notes saved to student_notes.csv")
