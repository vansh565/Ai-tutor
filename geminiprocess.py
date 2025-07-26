import google.generativeai as genai
genai.configure(api_key="AIzaSyD2eKhcIIS33G7uuvjA3VkI93bun_aELvQ")

def analyze_lecture(text, student_weak_topics=[]):
    prompt = f"""
You are an AI education assistant.
Here is the transcript of a class: {text}

Please:
1. Summarize it in clear points.
2. Generate doubts a student might ask.
3. Highlight concepts that may confuse students.
4. Explain deeply the following weak topics: {', '.join(student_weak_topics)}.
5. Skip or shorten already strong topics.

Return summary, doubts, keywords and topic tags.
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text
print("Gemini script started.")
