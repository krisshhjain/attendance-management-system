import { useState } from "react";
import FloatingLines from "./FloatingLines.jsx";
import AuthCard from "./AuthCard.jsx";
import "./AuthPage.css";

// Kept outside the component so their identity is stable across re-renders.
// FloatingLines rebuilds its WebGL scene when these props change, which would
// restart the intro every time the page re-renders.
const WAVES = ["top", "middle", "bottom"];
const LINES_GRADIENT = ["#e945f5", "#6f6f6f", "#6a6a6a"];

// Shared stage for the sign in pages: the animated lines background plus the
// sign in card, which appears once the intro has finished.
export function AuthPage(cardProps) {
  const [introDone, setIntroDone] = useState(false);

  return (
    <div className="auth-page">
      <FloatingLines
        enabledWaves={WAVES}
        lineCount={8}
        lineDistance={8}
        animationSpeed={1}
        interactive={true}
        bendRadius={8}
        bendStrength={-2}
        linesGradient={LINES_GRADIENT}
        onIntroComplete={() => setIntroDone(true)}
      />
      <AuthCard visible={introDone} {...cardProps} />
    </div>
  );
}
