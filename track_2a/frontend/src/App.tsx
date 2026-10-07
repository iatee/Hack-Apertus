import { useState } from "react";
import type { CreateSessionRequest, CreateSessionResponse, LanguageCode } from "./api";
import FeedbackScreen from "./screens/FeedbackScreen";
import InterviewScreen from "./screens/InterviewScreen";
import SetupScreen from "./screens/SetupScreen";

type Screen = "setup" | "interview" | "feedback";

export default function App() {
  const [screen, setScreen] = useState<Screen>("setup");
  const [language, setLanguage] = useState<LanguageCode>("de");
  const [session, setSession] = useState<CreateSessionResponse | null>(null);
  const [summary, setSummary] = useState("");

  function handleStarted(newSession: CreateSessionResponse, request: CreateSessionRequest, newSummary: string) {
    setLanguage(request.language);
    setSession(newSession);
    setSummary(newSummary);
    setScreen("interview");
  }

  function handleRestart() {
    setSession(null);
    setScreen("setup");
  }

  return (
    <div className="min-h-dvh">
      {screen === "setup" && (
        <SetupScreen language={language} onLanguageChange={setLanguage} onStarted={handleStarted} />
      )}

      {screen === "interview" && session && (
        <InterviewScreen
          session={session}
          language={language}
          summary={summary}
          onRestart={handleRestart}
          onFinished={() => setScreen("feedback")}
        />
      )}

      {screen === "feedback" && session && (
        <FeedbackScreen sessionId={session.session_id} language={language} onRestart={handleRestart} />
      )}
    </div>
  );
}
