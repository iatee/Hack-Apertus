import { useState } from "react";
import { api, type CreateSessionRequest, type CreateSessionResponse, type CriterionId, type LanguageCode } from "./api";
import FeedbackScreen from "./screens/FeedbackScreen";
import InterviewScreen from "./screens/InterviewScreen";
import SetupScreen from "./screens/SetupScreen";

type Screen = "setup" | "interview" | "feedback";

export default function App() {
  const [screen, setScreen] = useState<Screen>("setup");
  const [language, setLanguage] = useState<LanguageCode>("de");
  const [session, setSession] = useState<CreateSessionResponse | null>(null);
  const [summary, setSummary] = useState("");
  const [lastRequest, setLastRequest] = useState<CreateSessionRequest | null>(null);

  function handleStarted(newSession: CreateSessionResponse, request: CreateSessionRequest, newSummary: string) {
    setLanguage(request.language);
    setSession(newSession);
    setSummary(newSummary);
    setLastRequest(request);
    setScreen("interview");
  }

  /** "Practise this": same settings as the last interview, focused on the weakest criteria */
  async function handlePracticeAgain(focus: CriterionId[]) {
    if (!lastRequest) return;
    const request = { ...lastRequest, focus };
    handleStarted(await api.createSession(request), request, summary);
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
        <FeedbackScreen
          sessionId={session.session_id}
          language={language}
          onRestart={handleRestart}
          onPracticeAgain={handlePracticeAgain}
        />
      )}
    </div>
  );
}
