import { useEffect, useRef, useState } from "react";

import walk1 from "../assets/walk_cycle/walk_1.png";
import walk2 from "../assets/walk_cycle/walk_2.png";
import walk3 from "../assets/walk_cycle/walk_3.png";
import walk4 from "../assets/walk_cycle/walk_4.png";

const WALK_FRAMES = [walk1, walk2, walk3, walk4];

// ── Types ──────────────────────────────────────────────────────────────────
interface EEGData {
  delta: number;
  theta: number;
  alpha: number;
  beta: number;
  gamma: number;
  heart_rate: number;
  movement: number;
}

interface DreamFrame {
  source: "csv" | "simulated";
  eeg: EEGData;
  analysis?: {
    stage: string;
    intensity: number;
    mood: string;
  };
  stage: string;
  mood: string;
  intensity: number;
  prompt: string;
  selected_prompt_id?: number;
  world_name?: string;
  phase?: string;
  frame?: number;
  image: string | null;
  error?: string | null;
}

// ── Constants ──────────────────────────────────────────────────────────────
const STAGE_COLOR: Record<string, string> = {
  deep_sleep:  "#7c3aed",
  light_sleep: "#00e5ff",
  rem:         "#ff007f",
  transition:  "#00ff88",
};

const MOOD_COLOR: Record<string, string> = {
  calm:     "#00ff88",
  soft:     "#00e5ff",
  vivid:    "#ff007f",
  abstract: "#7c3aed",
  chaotic:  "#ff6a00",
};

const EEG_BANDS = [
  { key: "delta", label: "δ DELTA",  color: "#7c3aed" },
  { key: "theta", label: "θ THETA",  color: "#00e5ff" },
  { key: "alpha", label: "α ALPHA",  color: "#00ff88" },
  { key: "beta",  label: "β BETA",   color: "#ff007f" },
  { key: "gamma", label: "γ GAMMA",  color: "#ff6a00" },
] as const;

const PHASE_GLYPHS: Record<string, string> = {
  "as the dream begins to form": "◌",
  "deepening into the dream":    "◎",
  "fully immersed in the dream": "●",
  "approaching the edge of waking": "◑",
};

// ── Sub-components ─────────────────────────────────────────────────────────

function EEGBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: "#4a5080", fontFamily: "var(--font-mono)" }}>
          {label}
        </span>
        <span style={{ fontSize: 11, color, fontFamily: "var(--font-mono)" }}>
          {(value * 100).toFixed(0)}%
        </span>
      </div>
      <div
        style={{
          height: 6,
          background: "#0d0d2a",
          borderRadius: 3,
          overflow: "hidden",
          border: "1px solid #1a1a3e",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${value * 100}%`,
            background: `linear-gradient(90deg, ${color}88, ${color})`,
            borderRadius: 3,
            boxShadow: `0 0 8px ${color}88`,
            transition: "width 0.8s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </div>
    </div>
  );
}

function StageBadge({ stage }: { stage: string }) {
  const color = STAGE_COLOR[stage] ?? "#ffffff";
  const label = stage.replace("_", " ").toUpperCase();
  return (
    <div
      style={{
        display: "inline-block",
        padding: "4px 14px",
        border: `1px solid ${color}`,
        borderRadius: 3,
        color,
        fontSize: 12,
        fontFamily: "var(--font-hud)",
        letterSpacing: 2,
        boxShadow: `0 0 12px ${color}44`,
        background: `${color}11`,
        animation: "slide-in 0.4s ease",
      }}
    >
      {label}
    </div>
  );
}

function SourceBadge({ source }: { source?: DreamFrame["source"] }) {
  if (!source) {
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 10px",
          border: "1px solid #1a1a3e",
          borderRadius: 3,
          background: "#080818",
          color: "#4a5080",
          fontSize: 10,
          fontFamily: "var(--font-hud)",
          letterSpacing: 2,
        }}
      >
        AWAITING
      </div>
    );
  }

  const isCsv = source === "csv";
  const color = isCsv ? "#00ff88" : "#ff6a00";
  const label = isCsv ? "CSV DATA" : "SIMULATED";
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 10px",
        border: `1px solid ${color}66`,
        borderRadius: 3,
        background: `${color}11`,
        color,
        fontSize: 10,
        fontFamily: "var(--font-hud)",
        letterSpacing: 2,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 8px ${color}`,
        }}
      />
      {label}
    </div>
  );
}

function IntensityMeter({ value }: { value: number }) {
  const segments = 20;
  const filled = Math.round(value * segments);
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 10, color: "#4a5080", letterSpacing: 2 }}>INTENSITY</span>
        <span style={{ fontSize: 10, color: "#00e5ff" }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <div style={{ display: "flex", gap: 3 }}>
        {Array.from({ length: segments }).map((_, i) => {
          const active = i < filled;
          const hue = Math.round((i / segments) * 120);
          const segColor = active ? `hsl(${120 - hue * 1.2}, 100%, 55%)` : "#0d0d2a";
          return (
            <div
              key={i}
              style={{
                flex: 1,
                height: 8,
                background: segColor,
                borderRadius: 2,
                boxShadow: active ? `0 0 6px ${segColor}88` : "none",
                transition: "background 0.6s ease",
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

function ConnectionDot({ status }: { status: "connecting" | "live" | "error" }) {
  const colors = { connecting: "#ff6a00", live: "#00ff88", error: "#ff007f" };
  const color = colors[status];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 8px ${color}`,
          animation: status === "live" ? "pulse-ring 2s infinite" : "blink 1s infinite",
        }}
      />
      <span style={{ fontSize: 10, color, letterSpacing: 2, fontFamily: "var(--font-hud)" }}>
        {status.toUpperCase()}
      </span>
    </div>
  );
}

function DreamPhaseIndicator({ phase }: { phase: string }) {
  const glyph = PHASE_GLYPHS[phase] ?? "◌";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "6px 10px",
        border: "1px solid #1a1a3e",
        borderRadius: 4,
        background: "#080818",
        animation: "slide-in 0.5s ease",
      }}
    >
      <span style={{ fontSize: 14, color: "#7c3aed", lineHeight: 1 }}>{glyph}</span>
      <div>
        <div style={{ fontSize: 8, color: "#4a5080", letterSpacing: 2, marginBottom: 2 }}>
          DREAM PHASE
        </div>
        <div
          style={{
            fontSize: 10,
            color: "#c8d0e8",
            fontFamily: "var(--font-mono)",
            letterSpacing: 1,
          }}
        >
          {phase.toUpperCase()}
        </div>
      </div>
    </div>
  );
}

function WalkingCharacter() {
  const [frameIdx, setFrameIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setFrameIdx((i) => (i + 1) % 4), 160);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 56,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 6,
        pointerEvents: "none",
      }}
    >
      <img
        src={WALK_FRAMES[frameIdx]}
        alt=""
        aria-hidden
        style={{
          height: 120,
          imageRendering: "pixelated",
          transform: frameIdx % 2 === 1 ? "translateY(-5px)" : "translateY(0px)",
          transition: "transform 0.1s ease",
          filter: "drop-shadow(0 0 10px rgba(0,229,255,0.6))",
        }}
      />
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
export default function DreamCanvas() {
  const [frame, setFrame] = useState<DreamFrame | null>(null);
  const [prevImage, setPrevImage] = useState<string>("");
  const [currentImage, setCurrentImage] = useState<string>("");
  const [imageKey, setImageKey] = useState<number>(0);
  const [status, setStatus] = useState<"connecting" | "live" | "error">("connecting");
  const [frameCount, setFrameCount] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<string>("--:--:--");
  const [isGenerating, setIsGenerating] = useState<boolean>(true);
  const wsRef = useRef<WebSocket | null>(null);
  // Refs so event handlers always see the latest values (avoids stale closures)
  const currentImageRef = useRef<string>("");
  const isGeneratingRef = useRef<boolean>(true);

  useEffect(() => {
    const socket = new WebSocket("ws://localhost:8000/ws/dream");
    wsRef.current = socket;

    socket.onopen = () => setStatus("connecting");

    socket.onmessage = (event) => {
      const data: DreamFrame = JSON.parse(event.data);
      setStatus("live");
      setFrame(data);
      setFrameCount((n) => n + 1);
      setLastUpdate(new Date().toLocaleTimeString());

      if (data.image && isGeneratingRef.current) {
        const uri = `data:image/png;base64,${data.image}`;
        const prev = currentImageRef.current;
        currentImageRef.current = uri;
        if (prev) setPrevImage(prev);
        setCurrentImage(uri);
        setImageKey((k) => k + 1);
      }
    };

    socket.onerror = () => setStatus("error");
    socket.onclose = () => setStatus("error");

    return () => socket.close();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleGeneration = () => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const nextState = !isGeneratingRef.current;
    isGeneratingRef.current = nextState;
    setIsGenerating(nextState);
    ws.send(JSON.stringify({ action: nextState ? "resume" : "pause" }));
  };

  const eeg = frame?.eeg;
  const stageColor = STAGE_COLOR[frame?.stage ?? ""] ?? "#ffffff";
  const moodColor  = MOOD_COLOR[frame?.mood ?? ""]  ?? "#ffffff";

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "48px 1fr 36px",
        height: "100vh",
        width: "100vw",
        background: "var(--bg)",
        overflow: "hidden",
      }}
    >
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          borderBottom: "1px solid #1a1a3e",
          background: "#04040f",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 28,
              height: 28,
              border: "2px solid #00e5ff",
              borderRadius: 4,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 12px #00e5ff66",
            }}
          >
            <span style={{ fontSize: 14, color: "#00e5ff" }}>◈</span>
          </div>
          <span
            style={{
              fontFamily: "var(--font-hud)",
              fontSize: 13,
              letterSpacing: 4,
              color: "#00e5ff",
              animation: "flicker 8s infinite",
            }}
          >
            DREAM GENERATOR
          </span>
        </div>

        <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#4a5080", letterSpacing: 2 }}>
            FRAME{" "}
            <span style={{ color: "#00e5ff" }}>{String(frameCount).padStart(4, "0")}</span>
          </span>
          <span style={{ fontSize: 10, color: "#4a5080", letterSpacing: 2 }}>
            SYNC{" "}
            <span style={{ color: "#00ff88" }}>{lastUpdate}</span>
          </span>
          <SourceBadge source={frame?.source} />

          {/* ── Start / Stop button ── */}
          <button
            onClick={toggleGeneration}
            style={{
              padding: "4px 16px",
              border: `1px solid ${isGenerating ? "#ff007f" : "#00ff88"}`,
              borderRadius: 3,
              background: isGenerating ? "#ff007f11" : "#00ff8811",
              color: isGenerating ? "#ff007f" : "#00ff88",
              fontSize: 10,
              fontFamily: "var(--font-hud)",
              letterSpacing: 2,
              cursor: "pointer",
              boxShadow: isGenerating
                ? "0 0 10px #ff007f44"
                : "0 0 10px #00ff8844",
              transition: "all 0.3s ease",
            }}
          >
            {isGenerating ? "◉ PAUSE" : "▶ RESUME"}
          </button>
        </div>

        <ConnectionDot status={status} />
      </header>

      {/* ── Main content ───────────────────────────────────────────── */}
      <main
        style={{
          display: "grid",
          gridTemplateColumns: "220px 1fr 260px",
          overflow: "hidden",
        }}
      >
        {/* Left panel — EEG signals */}
        <aside
          style={{
            borderRight: "1px solid #1a1a3e",
            padding: "20px 16px",
            overflowY: "auto",
            background: "#04040f",
          }}
        >
          <div
            style={{
              fontSize: 9,
              color: "#4a5080",
              letterSpacing: 3,
              marginBottom: 20,
              fontFamily: "var(--font-hud)",
              borderBottom: "1px solid #1a1a3e",
              paddingBottom: 10,
            }}
          >
            EEG SIGNALS
          </div>

          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 9, color: "#4a5080", letterSpacing: 2, marginBottom: 8 }}>
              DATA SOURCE
            </div>
            <SourceBadge source={frame?.source} />
          </div>

          {EEG_BANDS.map(({ key, label, color }) => (
            <EEGBar
              key={key}
              label={label}
              value={eeg ? (eeg[key as keyof EEGData] as number) : 0}
              color={color}
            />
          ))}

          <div style={{ marginTop: 24 }}>
            <div
              style={{
                fontSize: 9,
                color: "#4a5080",
                letterSpacing: 3,
                marginBottom: 14,
                fontFamily: "var(--font-hud)",
                borderBottom: "1px solid #1a1a3e",
                paddingBottom: 10,
              }}
            >
              BIOMETRICS
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 10, color: "#4a5080" }}>HEART RATE</span>
                <span style={{ fontSize: 11, color: "#ff007f", fontFamily: "var(--font-mono)" }}>
                  {eeg?.heart_rate ?? "--"}{" "}
                  <span style={{ fontSize: 9, color: "#4a5080" }}>BPM</span>
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 10, color: "#4a5080" }}>MOVEMENT</span>
                <span style={{ fontSize: 11, color: "#00e5ff", fontFamily: "var(--font-mono)" }}>
                  {eeg ? (eeg.movement * 100).toFixed(0) : "--"}
                  <span style={{ fontSize: 9, color: "#4a5080" }}> %</span>
                </span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 28, opacity: 0.4 }}>
            <svg width="100%" height="40" viewBox="0 0 188 40">
              <polyline
                points={Array.from({ length: 19 }, (_, i) => {
                  const x = i * 10 + 4;
                  const y = 20 + Math.sin(i * 0.8 + Date.now() * 0.001) * 14;
                  return `${x},${y}`;
                }).join(" ")}
                fill="none"
                stroke="#00e5ff"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        </aside>

        {/* Center — Dream image with crossfade */}
        <section
          style={{
            position: "relative",
            background: "#020208",
            overflow: "hidden",
          }}
        >
          {/* Animated grid background */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundImage:
                "linear-gradient(#0d0d2a 1px, transparent 1px), linear-gradient(90deg, #0d0d2a 1px, transparent 1px)",
              backgroundSize: "40px 40px",
              animation: "grid-move 8s linear infinite",
              opacity: 0.4,
            }}
          />

          {/* Corner brackets */}
          {[
            { top: 16, left: 16 },
            { top: 16, right: 16 },
            { bottom: 16, left: 16 },
            { bottom: 16, right: 16 },
          ].map((pos, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                ...pos,
                width: 24,
                height: 24,
                borderColor: "#00e5ff",
                borderStyle: "solid",
                borderWidth: 0,
                borderTopWidth:    pos.top    !== undefined ? 2 : 0,
                borderBottomWidth: pos.bottom !== undefined ? 2 : 0,
                borderLeftWidth:   pos.left   !== undefined ? 2 : 0,
                borderRightWidth:  pos.right  !== undefined ? 2 : 0,
                opacity: 0.6,
                zIndex: 5,
              }}
            />
          ))}

          {/* ── Crossfade image layers ── */}
          {prevImage && (
            <img
              key={`prev-${imageKey}`}
              src={prevImage}
              alt=""
              aria-hidden
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                animation: "crossfade-out 1.6s ease-in-out forwards",
                zIndex: 1,
              }}
            />
          )}

          {currentImage ? (
            <img
              key={`curr-${imageKey}`}
              src={currentImage}
              alt="Dream"
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                animation: "crossfade-in 1.6s ease-in-out forwards",
                zIndex: 2,
              }}
            />
          ) : (
            <div
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 16,
                opacity: 0.4,
                zIndex: 1,
              }}
            >
              <div
                style={{
                  width: 64,
                  height: 64,
                  border: "2px solid #00e5ff",
                  borderRadius: "50%",
                  borderTopColor: "transparent",
                  animation: "spin 1.2s linear infinite",
                }}
              />
              <span style={{ fontSize: 11, letterSpacing: 3, color: "#00e5ff" }}>
                INITIALIZING NEURAL FEED…
              </span>
            </div>
          )}

          {/* World name overlay */}
          {frame?.world_name && (
            <div
              style={{
                position: "absolute",
                top: 24,
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 5,
                padding: "5px 18px",
                border: "1px solid #00e5ff55",
                borderRadius: 4,
                background: "rgba(4,4,15,0.72)",
                color: "#00e5ff",
                fontSize: 11,
                fontFamily: "var(--font-hud)",
                letterSpacing: 3,
                backdropFilter: "blur(4px)",
                whiteSpace: "nowrap",
              }}
            >
              {frame.world_name.toUpperCase()}
            </div>
          )}

          {/* Walking character */}
          <WalkingCharacter />

          {/* Paused overlay */}
          {!isGenerating && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(0,0,0,0.55)",
                zIndex: 10,
              }}
            >
              <div
                style={{
                  padding: "12px 28px",
                  border: "1px solid #00ff8888",
                  borderRadius: 4,
                  background: "#00ff8811",
                  color: "#00ff88",
                  fontSize: 12,
                  fontFamily: "var(--font-hud)",
                  letterSpacing: 3,
                  boxShadow: "0 0 20px #00ff8844",
                }}
              >
                ▶ DREAM PAUSED
              </div>
            </div>
          )}
        </section>

        {/* Right panel — Neural state */}
        <aside
          style={{
            borderLeft: "1px solid #1a1a3e",
            padding: "20px 16px",
            overflowY: "auto",
            background: "#04040f",
            display: "flex",
            flexDirection: "column",
            gap: 20,
          }}
        >
          <div
            style={{
              fontSize: 9,
              color: "#4a5080",
              letterSpacing: 3,
              fontFamily: "var(--font-hud)",
              borderBottom: "1px solid #1a1a3e",
              paddingBottom: 10,
            }}
          >
            NEURAL STATE
          </div>

          {/* Dream phase */}
          {frame?.phase && <DreamPhaseIndicator phase={frame.phase} />}

          {/* Stage */}
          <div>
            <div style={{ fontSize: 9, color: "#4a5080", letterSpacing: 2, marginBottom: 8 }}>
              SLEEP STAGE
            </div>
            {frame?.stage ? (
              <StageBadge stage={frame.stage} />
            ) : (
              <span style={{ fontSize: 11, color: "#4a5080" }}>AWAITING DATA</span>
            )}
          </div>

          {/* Mood */}
          <div>
            <div style={{ fontSize: 9, color: "#4a5080", letterSpacing: 2, marginBottom: 8 }}>
              MOOD
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: moodColor,
                  boxShadow: `0 0 8px ${moodColor}`,
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontFamily: "var(--font-hud)",
                  fontSize: 13,
                  color: moodColor,
                  letterSpacing: 2,
                  textTransform: "uppercase",
                  animation: frame?.mood ? "slide-in 0.4s ease" : "none",
                }}
              >
                {frame?.mood ?? "—"}
              </span>
            </div>
          </div>

          {/* Dream world */}
          <div>
            <div style={{ fontSize: 9, color: "#4a5080", letterSpacing: 2, marginBottom: 8 }}>
              DREAM WORLD
            </div>
            <div
              style={{
                fontSize: 13,
                color: "#00e5ff",
                fontFamily: "var(--font-hud)",
                letterSpacing: 2,
                animation: frame?.world_name ? "slide-in 0.4s ease" : "none",
              }}
            >
              {frame?.world_name ? frame.world_name.toUpperCase() : "—"}
            </div>
          </div>

          {/* Intensity meter */}
          {frame !== null && <IntensityMeter value={frame.intensity} />}

          <div style={{ borderTop: "1px solid #1a1a3e" }} />

          {/* Prompt */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 9, color: "#4a5080", letterSpacing: 2, marginBottom: 10 }}>
              ACTIVE PROMPT
            </div>
            <p
              style={{
                fontSize: 11,
                color: "#6a7090",
                lineHeight: 1.7,
                fontFamily: "var(--font-mono)",
                animation: frame?.prompt ? "slide-in 0.5s ease" : "none",
              }}
            >
              {frame?.prompt ?? "Waiting for neural signal…"}
            </p>
          </div>

          {/* Error notice */}
          {frame?.error && (
            <div
              style={{
                padding: "8px 12px",
                border: "1px solid #ff007f55",
                borderRadius: 4,
                background: "#ff007f11",
                fontSize: 10,
                color: "#ff007f",
                lineHeight: 1.6,
              }}
            >
              {frame.error}
            </div>
          )}
        </aside>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          borderTop: "1px solid #1a1a3e",
          background: "#04040f",
          fontSize: 9,
          color: "#4a5080",
          letterSpacing: 2,
        }}
      >
        <span>CLOUDFLARE WORKERS AI  ·  STABLE DIFFUSION XL</span>
        <span>EEG CSV/SIM  ·  DREAM GEN  ·  TEMPORAL COHERENCE</span>
        <span style={{ color: "#1a1a3e" }}>◈◈◈</span>
      </footer>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
