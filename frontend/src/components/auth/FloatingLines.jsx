import { useEffect, useRef, useState } from "react";
import {
  Clock,
  Mesh,
  OrthographicCamera,
  PlaneGeometry,
  Scene,
  ShaderMaterial,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";

import "./FloatingLines.css";

const vertexShader = `
precision highp float;

void main() {
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const fragmentShader = `
precision highp float;

uniform float iTime;
uniform vec3  iResolution;
uniform float animationSpeed;

uniform bool enableTop;
uniform bool enableMiddle;
uniform bool enableBottom;

uniform int topLineCount;
uniform int middleLineCount;
uniform int bottomLineCount;

uniform float topLineDistance;
uniform float middleLineDistance;
uniform float bottomLineDistance;

uniform vec3 topWavePosition;
uniform vec3 middleWavePosition;
uniform vec3 bottomWavePosition;

uniform vec2 iMouse;
uniform bool interactive;
uniform float bendRadius;
uniform float bendStrength;
uniform float bendInfluence;

uniform bool parallax;
uniform float parallaxStrength;
uniform vec2 parallaxOffset;

uniform vec3 lineGradient[8];
uniform int lineGradientCount;
uniform vec3 backgroundColor;
uniform bool lightMode;

// Entrance animation. Each intro* time is "seconds since this wave group
// began entering" (negative while it is still waiting its turn).
uniform float introTop;
uniform float introMiddle;
uniform float introBottom;
uniform float introLineDuration;
uniform float introLineStagger;
uniform float introSpreadStart;
uniform float introSpreadDuration;
uniform float introSwell;
uniform float introDrift;
uniform float introHeadGlow;

const vec3 BLACK = vec3(0.0);
const vec3 PINK  = vec3(233.0, 71.0, 245.0) / 255.0;
const vec3 BLUE  = vec3(47.0,  75.0, 162.0) / 255.0;

// Soft trail behind the sweep head, in local units. The head must travel this
// far past the screen edge before a strand counts as fully drawn.
const float TRAIL = 1.4;

mat2 rotate(float r) {
  return mat2(cos(r), sin(r), -sin(r), cos(r));
}

vec3 background_color(vec2 uv) {
  vec3 col = vec3(0.0);

  float y = sin(uv.x - 0.2) * 0.3 - 0.1;
  float m = uv.y - y;

  col += mix(BLUE, BLACK, smoothstep(0.0, 1.0, abs(m)));
  col += mix(PINK, BLACK, smoothstep(0.0, 1.0, abs(m - 0.8)));
  return col * 0.5;
}

vec3 getLineColor(float t, vec3 baseColor) {
  if (lineGradientCount <= 0) {
    return baseColor;
  }

  vec3 gradientColor;

  if (lineGradientCount == 1) {
    gradientColor = lineGradient[0];
  } else {
    float clampedT = clamp(t, 0.0, 0.9999);
    float scaled = clampedT * float(lineGradientCount - 1);
    int idx = int(floor(scaled));
    float f = fract(scaled);
    int idx2 = min(idx + 1, lineGradientCount - 1);

    vec3 c1 = lineGradient[idx];
    vec3 c2 = lineGradient[idx2];

    gradientColor = mix(c1, c2, f);
  }

  return gradientColor * 0.5;
}

// Quintic ease in-out: zero velocity and acceleration at both ends, so the
// head emerges from the edge gently and glides to a stop instead of snapping.
float easeInOut(float p) {
  return p * p * p * (p * (p * 6.0 - 15.0) + 10.0);
}

float easeOut(float p) {
  return 1.0 - pow(1.0 - p, 3.0);
}

// Raw entrance progress (0..1) for strand fi of a group whose entrance began
// gt seconds ago. Strands set off a little after one another.
float introProgress(float gt, float fi) {
  return clamp((gt - fi * introLineStagger) / max(introLineDuration, 0.001), 0.0, 1.0);
}

// How far the strands of a group have unfurled from a single beam into the
// full bundle (0..1).
float introSpread(float gt) {
  float p = clamp((gt - introSpreadStart) / max(introSpreadDuration, 0.001), 0.0, 1.0);
  return easeInOut(p);
}

// Draws a strand along its own length: a glowing head travels from one edge
// of the screen to the other and the strand fades in behind it.
// x is the local x of the strand; center is its local x at mid screen.
float introMask(float x, float center, float progress) {
  float reach = length(iResolution.xy) / iResolution.y + 0.6;
  float head = mix(center - reach - 0.4, center + reach + TRAIL + 0.1, easeInOut(progress));
  float d = x - head;
  float trail = 1.0 - smoothstep(-TRAIL, 0.1, d);
  float bead = exp(-d * d * 18.0) * introHeadGlow;
  return trail + bead;
}

// Keeps the perceived brightness steady while a group is collapsed into one
// beam: n identical strands stacked on top of each other would otherwise be
// n times brighter than the settled bundle.
float introGain(float spread, float n) {
  return 1.0 / (1.0 + (n - 1.0) * (1.0 - spread) * 0.8);
}

float wave(vec2 uv, float offset, vec2 screenUv, vec2 mouseUv, bool shouldBend, float ampScale) {
  float time = iTime * animationSpeed;

  float x_offset   = offset;
  float x_movement = time * 0.1;
  float amp        = sin(offset + time * 0.2) * 0.3 * ampScale;
  float y          = sin(uv.x + x_offset + x_movement) * amp;

  if (shouldBend) {
    vec2 d = screenUv - mouseUv;
    float influence = exp(-dot(d, d) * bendRadius); // radial falloff around cursor
    float bendOffset = (mouseUv.y - screenUv.y) * influence * bendStrength * bendInfluence;
    y += bendOffset;
  }

  float m = uv.y - y;
  return 0.0175 / max(abs(m) + 0.01, 1e-3) + 0.01;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
  vec2 baseUv = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
  baseUv.y *= -1.0;

  if (parallax) {
    baseUv += parallaxOffset;
  }

  vec3 col = vec3(0.0);

  vec3 b = lineGradientCount > 0 ? vec3(0.0) : background_color(baseUv);

  vec2 mouseUv = vec2(0.0);
  if (interactive) {
    mouseUv = (2.0 * iMouse - iResolution.xy) / iResolution.y;
    mouseUv.y *= -1.0;
  }

  if (enableBottom) {
    float spread = introSpread(introBottom);
    float gain = introGain(spread, float(bottomLineCount));

    for (int i = 0; i < bottomLineCount; ++i) {
      float fi = float(i);
      float t = fi / max(float(bottomLineCount - 1), 1.0);
      vec3 lineCol = getLineColor(t, b);

      float progress = introProgress(introBottom, fi);
      float settle = easeOut(progress);
      float fs = fi * spread;
      float center = bottomLineDistance * fs + bottomWavePosition.x;

      float angle = bottomWavePosition.z * log(length(baseUv) + 1.0);
      vec2 ruv = baseUv * rotate(angle);
      vec2 luv = ruv + vec2(center, bottomWavePosition.y - introDrift * (1.0 - settle));

      col += lineCol * wave(
        luv,
        1.5 + 0.2 * fs,
        baseUv,
        mouseUv,
        interactive,
        mix(introSwell, 1.0, settle)
      ) * introMask(luv.x, center, progress) * gain * 0.2;
    }
  }

  if (enableMiddle) {
    float spread = introSpread(introMiddle);
    float gain = introGain(spread, float(middleLineCount));

    for (int i = 0; i < middleLineCount; ++i) {
      float fi = float(i);
      float t = fi / max(float(middleLineCount - 1), 1.0);
      vec3 lineCol = getLineColor(t, b);

      float progress = introProgress(introMiddle, fi);
      float settle = easeOut(progress);
      float fs = fi * spread;
      float center = middleLineDistance * fs + middleWavePosition.x;

      float angle = middleWavePosition.z * log(length(baseUv) + 1.0);
      vec2 ruv = baseUv * rotate(angle);
      vec2 luv = ruv + vec2(center, middleWavePosition.y + introDrift * (1.0 - settle));

      col += lineCol * wave(
        luv,
        2.0 + 0.15 * fs,
        baseUv,
        mouseUv,
        interactive,
        mix(introSwell, 1.0, settle)
      ) * introMask(luv.x, center, progress) * gain;
    }
  }

  if (enableTop) {
    float spread = introSpread(introTop);
    float gain = introGain(spread, float(topLineCount));

    for (int i = 0; i < topLineCount; ++i) {
      float fi = float(i);
      float t = fi / max(float(topLineCount - 1), 1.0);
      vec3 lineCol = getLineColor(t, b);

      float progress = introProgress(introTop, fi);
      float settle = easeOut(progress);
      float fs = fi * spread;
      float center = topLineDistance * fs + topWavePosition.x;

      float angle = topWavePosition.z * log(length(baseUv) + 1.0);
      vec2 ruv = baseUv * rotate(angle);
      ruv.x *= -1.0;
      vec2 luv = ruv + vec2(center, topWavePosition.y - introDrift * (1.0 - settle));

      col += lineCol * wave(
        luv,
        1.0 + 0.2 * fs,
        baseUv,
        mouseUv,
        interactive,
        mix(introSwell, 1.0, settle)
      ) * introMask(luv.x, center, progress) * gain * 0.1;
    }
  }

if (lightMode) {
  vec3 energy = max(col, vec3(0.0));
  float peak = max(energy.r, max(energy.g, energy.b));
  float coverage = smoothstep(0.018, 0.5, peak);
  vec3 chroma = clamp(energy / max(peak, 0.0001), 0.0, 1.0);
  chroma = pow(chroma, vec3(1.35));
  float chromaPeak = max(chroma.r, max(chroma.g, chroma.b));
  chroma /= max(chromaPeak, 0.0001);
  vec3 ink = mix(chroma, clamp(chroma * 0.82, 0.0, 1.0), smoothstep(0.5, 1.0, coverage));
  fragColor = vec4(mix(vec3(1.0), ink, coverage * 0.94), 1.0);
} else {
    fragColor = vec4(col, 1.0);
  }
}

void main() {
  vec4 color = vec4(0.0);
  mainImage(color, gl_FragCoord.xy);
  gl_FragColor = color;
}
`;

const MAX_GRADIENT_STOPS = 8;
const WAVE_TYPES = ["top", "middle", "bottom"];

// Module-level so the default keeps one identity across renders.
const DEFAULT_BOTTOM_WAVE = { x: 2.0, y: -0.7, rotate: -1 };

// A group this many seconds into its entrance is fully drawn. Used to skip the intro.
const INTRO_DONE = 1000;

// sessionStorage key used when `oncePerSession` is on.
const SESSION_KEY = "floating-lines:intro-played";

// If WebGL is unavailable the card is shown right away and the scene is
// attempted again this many times, this far apart.
const WEBGL_RETRIES = 1;
const WEBGL_RETRY_DELAY_MS = 2000;

// The sweep head follows a quintic ease in-out, so the last stretch of
// `lineDuration` is imperceptible settling. A strand reads as fully drawn at
// roughly this fraction of its duration; the same goes for the unfurl.
const VISUAL_END = 0.85;

// Timings are in seconds. `delays` is when each wave group starts entering,
// measured from mount. Each strand of a group takes `lineDuration` to sweep
// across the screen and strands set off `lineStagger` apart. The group starts
// as one collapsed beam and unfurls into its strands between `spreadStart` and
// `spreadStart + spreadDuration`. `swell` scales the wave amplitude at the
// start of the entrance, `drift` is how far a strand slides into place and
// `headGlow` is the brightness of the travelling head.
// `oncePerSession` skips the intro on later mounts within the same tab session.
const DEFAULT_INTRO = {
  delays: { middle: 0.3, bottom: 0.9, top: 1.4 },
  lineDuration: 1.8,
  lineStagger: 0.05,
  spreadStart: 0.5,
  spreadDuration: 1.4,
  swell: 1.4,
  drift: 0.25,
  headGlow: 2.6,
  oncePerSession: false,
};

function resolveIntro(intro) {
  if (intro === false) return null;
  const custom = intro && typeof intro === "object" ? intro : {};
  return {
    ...DEFAULT_INTRO,
    ...custom,
    delays: { ...DEFAULT_INTRO.delays, ...(custom.delays ?? {}) },
  };
}

function readSession(key) {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeSession(key, value) {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // Storage can be unavailable (private mode, blocked). The intro simply replays.
  }
}

// Development aid: `?introAt=2.4` freezes the intro at that second so a
// single moment of the choreography can be inspected or screenshotted.
function readFrozenIntroTime() {
  if (!import.meta.env.DEV || typeof window === "undefined") return null;
  const value = parseFloat(new URLSearchParams(window.location.search).get("introAt"));
  return Number.isFinite(value) ? value : null;
}

function hexToVec3(hex) {
  let value = hex.trim();

  if (value.startsWith("#")) {
    value = value.slice(1);
  }

  let r = 255;
  let g = 255;
  let b = 255;

  if (value.length === 3) {
    r = parseInt(value[0] + value[0], 16);
    g = parseInt(value[1] + value[1], 16);
    b = parseInt(value[2] + value[2], 16);
  } else if (value.length === 6) {
    r = parseInt(value.slice(0, 2), 16);
    g = parseInt(value.slice(2, 4), 16);
    b = parseInt(value.slice(4, 6), 16);
  }

  return new Vector3(r / 255, g / 255, b / 255);
}

export default function FloatingLines({
  linesGradient,
  enabledWaves = ["top", "middle", "bottom"],
  lineCount = [6],
  lineDistance = [5],
  topWavePosition,
  middleWavePosition,
  bottomWavePosition = DEFAULT_BOTTOM_WAVE,
  animationSpeed = 1,
  interactive = true,
  bendRadius = 5.0,
  bendStrength = -0.5,
  mouseDamping = 0.05,
  parallax = true,
  parallaxStrength = 0.2,
  mixBlendMode = "screen",
  backgroundColor = "#000000",
  lightMode = false,
  // true plays the default entrance, false skips it, an object overrides DEFAULT_INTRO.
  intro = true,
  // Called once, when every enabled wave group reads as fully entered.
  onIntroComplete,
}) {
  const containerRef = useRef(null);
  // Bumped when a failed WebGL start is retried, which re-runs the scene effect.
  const [webglAttempt, setWebglAttempt] = useState(0);
  const targetMouseRef = useRef(new Vector2(-1000, -1000));
  const currentMouseRef = useRef(new Vector2(-1000, -1000));
  const targetInfluenceRef = useRef(0);
  const currentInfluenceRef = useRef(0);
  const targetParallaxRef = useRef(new Vector2(0, 0));
  const currentParallaxRef = useRef(new Vector2(0, 0));

  // Kept in a ref so a new callback identity does not rebuild the scene.
  const onIntroCompleteRef = useRef(onIntroComplete);
  onIntroCompleteRef.current = onIntroComplete;

  // Object and array props are compared by value, not identity. Without this,
  // an inline literal (or a default parameter object) is a new reference on
  // every render of the parent, which would tear down the WebGL scene and
  // replay the intro each time the parent re-renders.
  const configKey = JSON.stringify({
    linesGradient,
    enabledWaves,
    lineCount,
    lineDistance,
    topWavePosition,
    middleWavePosition,
    bottomWavePosition,
    intro,
  });

  const getLineCount = (waveType) => {
    if (typeof lineCount === "number") return lineCount;
    if (!enabledWaves.includes(waveType)) return 0;
    const index = enabledWaves.indexOf(waveType);
    return lineCount[index] ?? 6;
  };

  const getLineDistance = (waveType) => {
    if (typeof lineDistance === "number") return lineDistance;
    if (!enabledWaves.includes(waveType)) return 0.1;
    const index = enabledWaves.indexOf(waveType);
    return lineDistance[index] ?? 0.1;
  };

  const topLineCount = enabledWaves.includes("top") ? getLineCount("top") : 0;
  const middleLineCount = enabledWaves.includes("middle") ? getLineCount("middle") : 0;
  const bottomLineCount = enabledWaves.includes("bottom") ? getLineCount("bottom") : 0;

  const topLineDistance = enabledWaves.includes("top") ? getLineDistance("top") * 0.01 : 0.01;
  const middleLineDistance = enabledWaves.includes("middle")
    ? getLineDistance("middle") * 0.01
    : 0.01;
  const bottomLineDistance = enabledWaves.includes("bottom")
    ? getLineDistance("bottom") * 0.01
    : 0.01;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let active = true;

    const reduceMotion =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let introConfig = reduceMotion ? null : resolveIntro(intro);

    if (introConfig?.oncePerSession && readSession(SESSION_KEY) === "1") {
      introConfig = null;
    }

    const frozenIntroTime = readFrozenIntroTime();

    const lineCounts = { top: topLineCount, middle: middleLineCount, bottom: bottomLineCount };

    // Seconds from mount until the last enabled group reads as fully entered.
    const introEnd = introConfig
      ? WAVE_TYPES.filter((w) => enabledWaves.includes(w)).reduce((end, w) => {
          const start = introConfig.delays[w] ?? 0;
          const strands = Math.max(lineCounts[w] - 1, 0);
          const sweepEnd =
            start + introConfig.lineDuration * VISUAL_END + strands * introConfig.lineStagger;
          const spreadEnd =
            start + introConfig.spreadStart + introConfig.spreadDuration * VISUAL_END;
          return Math.max(end, sweepEnd, spreadEnd);
        }, 0)
      : 0;

    let introFired = false;

    const scene = new Scene();

    const camera = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
    camera.position.z = 1;

    let renderer;
    try {
      renderer = new WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      // WebGL is blocked or unsupported. Never leave the page empty: reveal the
      // card immediately, then try to bring the background up once more.
      if (typeof onIntroCompleteRef.current === "function") {
        onIntroCompleteRef.current();
      }
      let retry = 0;
      if (webglAttempt < WEBGL_RETRIES) {
        retry = window.setTimeout(() => setWebglAttempt((n) => n + 1), WEBGL_RETRY_DELAY_MS);
      }
      return () => {
        if (retry) window.clearTimeout(retry);
      };
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    container.appendChild(renderer.domElement);

    const uniforms = {
      iTime: { value: 0 },
      iResolution: { value: new Vector3(1, 1, 1) },
      animationSpeed: { value: animationSpeed },

      enableTop: { value: enabledWaves.includes("top") },
      enableMiddle: { value: enabledWaves.includes("middle") },
      enableBottom: { value: enabledWaves.includes("bottom") },

      topLineCount: { value: topLineCount },
      middleLineCount: { value: middleLineCount },
      bottomLineCount: { value: bottomLineCount },

      topLineDistance: { value: topLineDistance },
      middleLineDistance: { value: middleLineDistance },
      bottomLineDistance: { value: bottomLineDistance },

      topWavePosition: {
        value: new Vector3(
          topWavePosition?.x ?? 10.0,
          topWavePosition?.y ?? 0.5,
          topWavePosition?.rotate ?? -0.4,
        ),
      },
      middleWavePosition: {
        value: new Vector3(
          middleWavePosition?.x ?? 5.0,
          middleWavePosition?.y ?? 0.0,
          middleWavePosition?.rotate ?? 0.2,
        ),
      },
      bottomWavePosition: {
        value: new Vector3(
          bottomWavePosition?.x ?? 2.0,
          bottomWavePosition?.y ?? -0.7,
          bottomWavePosition?.rotate ?? 0.4,
        ),
      },

      iMouse: { value: new Vector2(-1000, -1000) },
      interactive: { value: interactive },
      bendRadius: { value: bendRadius },
      bendStrength: { value: bendStrength },
      bendInfluence: { value: 0 },

      parallax: { value: parallax },
      parallaxStrength: { value: parallaxStrength },
      parallaxOffset: { value: new Vector2(0, 0) },

      lineGradient: {
        value: Array.from({ length: MAX_GRADIENT_STOPS }, () => new Vector3(1, 1, 1)),
      },
      lineGradientCount: { value: 0 },
      backgroundColor: { value: hexToVec3(backgroundColor) },
      lightMode: { value: lightMode },

      introTop: { value: introConfig ? -introConfig.delays.top : INTRO_DONE },
      introMiddle: { value: introConfig ? -introConfig.delays.middle : INTRO_DONE },
      introBottom: { value: introConfig ? -introConfig.delays.bottom : INTRO_DONE },
      introLineDuration: { value: introConfig?.lineDuration ?? DEFAULT_INTRO.lineDuration },
      introLineStagger: { value: introConfig?.lineStagger ?? DEFAULT_INTRO.lineStagger },
      introSpreadStart: { value: introConfig?.spreadStart ?? DEFAULT_INTRO.spreadStart },
      introSpreadDuration: { value: introConfig?.spreadDuration ?? DEFAULT_INTRO.spreadDuration },
      introSwell: { value: introConfig?.swell ?? DEFAULT_INTRO.swell },
      introDrift: { value: introConfig?.drift ?? DEFAULT_INTRO.drift },
      introHeadGlow: { value: introConfig?.headGlow ?? DEFAULT_INTRO.headGlow },
    };

    if (linesGradient && linesGradient.length > 0) {
      const stops = linesGradient.slice(0, MAX_GRADIENT_STOPS);
      uniforms.lineGradientCount.value = stops.length;

      stops.forEach((hex, i) => {
        const color = hexToVec3(hex);
        uniforms.lineGradient.value[i].set(color.x, color.y, color.z);
      });
    }

    const material = new ShaderMaterial({
      uniforms,
      vertexShader,
      fragmentShader,
    });

    const geometry = new PlaneGeometry(2, 2);
    const mesh = new Mesh(geometry, material);
    scene.add(mesh);

    const clock = new Clock();

    const setSize = () => {
      if (!active) return;
      const width = container.clientWidth || 1;
      const height = container.clientHeight || 1;

      renderer.setSize(width, height, false);

      const canvasWidth = renderer.domElement.width;
      const canvasHeight = renderer.domElement.height;
      uniforms.iResolution.value.set(canvasWidth, canvasHeight, 1);
    };

    setSize();

    const ro =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            if (!active) return;
            setSize();
          })
        : null;

    if (ro) ro.observe(container);

    const handlePointerMove = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const dpr = renderer.getPixelRatio();

      targetMouseRef.current.set(x * dpr, (rect.height - y) * dpr);
      targetInfluenceRef.current = 1.0;

      if (parallax) {
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const offsetX = (x - centerX) / rect.width;
        const offsetY = -(y - centerY) / rect.height;
        targetParallaxRef.current.set(offsetX * parallaxStrength, offsetY * parallaxStrength);
      }
    };

    const handlePointerLeave = () => {
      targetInfluenceRef.current = 0.0;
    };

    if (interactive) {
      renderer.domElement.addEventListener("pointermove", handlePointerMove);
      renderer.domElement.addEventListener("pointerleave", handlePointerLeave);
    }

    // If the GPU context drops mid-intro the render loop stalls, so make sure
    // the card still appears. preventDefault lets the browser restore the
    // context and rendering resumes on its own.
    const handleContextLost = (event) => {
      event.preventDefault();
      if (!introFired) {
        introFired = true;
        if (typeof onIntroCompleteRef.current === "function") {
          onIntroCompleteRef.current();
        }
      }
    };
    renderer.domElement.addEventListener("webglcontextlost", handleContextLost);

    let raf = 0;
    const renderLoop = () => {
      if (!active) return;

      const elapsed = frozenIntroTime ?? clock.getElapsedTime();
      uniforms.iTime.value = elapsed;

      if (introConfig) {
        uniforms.introTop.value = elapsed - introConfig.delays.top;
        uniforms.introMiddle.value = elapsed - introConfig.delays.middle;
        uniforms.introBottom.value = elapsed - introConfig.delays.bottom;
      }

      if (!introFired && elapsed >= introEnd) {
        introFired = true;
        if (introConfig?.oncePerSession) writeSession(SESSION_KEY, "1");
        if (typeof onIntroCompleteRef.current === "function") {
          onIntroCompleteRef.current();
        }
      }

      if (interactive) {
        currentMouseRef.current.lerp(targetMouseRef.current, mouseDamping);
        uniforms.iMouse.value.copy(currentMouseRef.current);

        currentInfluenceRef.current +=
          (targetInfluenceRef.current - currentInfluenceRef.current) * mouseDamping;
        uniforms.bendInfluence.value = currentInfluenceRef.current;
      }

      if (parallax) {
        currentParallaxRef.current.lerp(targetParallaxRef.current, mouseDamping);
        uniforms.parallaxOffset.value.copy(currentParallaxRef.current);
      }

      renderer.render(scene, camera);
      raf = requestAnimationFrame(renderLoop);
    };
    renderLoop();

    return () => {
      active = false;

      cancelAnimationFrame(raf);

      if (ro) ro.disconnect();

      if (interactive) {
        renderer.domElement.removeEventListener("pointermove", handlePointerMove);
        renderer.domElement.removeEventListener("pointerleave", handlePointerLeave);
      }
      renderer.domElement.removeEventListener("webglcontextlost", handleContextLost);

      geometry.dispose();
      material.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      if (renderer.domElement.parentElement) {
        renderer.domElement.parentElement.removeChild(renderer.domElement);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    configKey,
    animationSpeed,
    interactive,
    bendRadius,
    bendStrength,
    mouseDamping,
    parallax,
    parallaxStrength,
    backgroundColor,
    lightMode,
    webglAttempt,
  ]);

  return (
    <div
      ref={containerRef}
      className="floating-lines-container"
      style={{
        mixBlendMode: lightMode ? "normal" : mixBlendMode,
      }}
    />
  );
}
