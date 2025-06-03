import nltk
from textblob import TextBlob
import language_tool_python
import speech_recognition as sr


class SpellCheckerModule:
    def __init__(self):
        # Initialize LanguageTool for English (US)
        self.tool = language_tool_python.LanguageTool('en-US')

    def correct_spell(self, text):
        # Correct spelling word by word using TextBlob
        words = text.split()
        corrected_words = [str(TextBlob(word).correct()) for word in words]
        return " ".join(corrected_words)

    def correct_grammar(self, text):
        # Detect grammar issues using LanguageTool
        matches = self.tool.check(text)
        
        # Apply all grammar corrections
        corrected_text = language_tool_python.utils.correct(text, matches)

        # Create a detailed report of grammar mistakes
        grammar_issues = []
        for match in matches:
            issue = {
                "message": match.message,
                "error_text": text[match.offset:match.offset + match.errorLength],
                "suggestions": match.replacements,
                "rule_id": match.ruleId
            }
            grammar_issues.append(issue)

        return corrected_text, grammar_issues
    
    def voice_to_text(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("🎤 Speak now...")
            audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio)
            print("You said:", text)
            return text
        except sr.UnknownValueError:
            return "Could not understand the audio."
        except sr.RequestError:
            return "Speech recognition service unavailable."
