# TruthLens Demonstration Guide

This guide outlines 3 ready-to-test live demonstration cases showcasing the full multimodal verification and credibility classification capabilities of **TruthLens**.

---

## 📌 Case 1: Real Verified News (Primary Outlets)

### Input
- **Headline**: `ISRO successfully launches Chandrayaan-3 lunar mission`
- **Body**:
  ```text
  The Indian Space Research Organisation launched the Chandrayaan-3 spacecraft from the Satish Dhawan Space Centre on July 14, 2023, heading towards the south pole of the Moon.
  ```
- **Image**: None (or official ISRO launch photo)

### Expected System Behavior
1. **Text Analysis**:
   - Clickbait Score: Low (< 20%)
   - Headline-Body Consistency: High (>= 90%)
   - Key Claims: `["ISRO launched Chandrayaan-3", "Launched from Satish Dhawan Space Centre on July 14, 2023", "Heading towards lunar south pole"]`
2. **Web Retrieval**: Finds ISRO, BBC, Wikipedia, or Reuters reporting the mission.
3. **Claim Verification**: `Supported` with reputable source citations.
4. **Final Verdict**: **REAL** (Credibility score: 85–100%, Confidence: 80–95%).

---

## 📌 Case 2: Sensational Clickbait

### Input
- **Headline**: `YOU WON'T BELIEVE WHAT HAPPENS NEXT! DOCTORS TERRIFIED BY THIS ONE WEIRD OVERNIGHT TRICK!`
- **Body**: (Leave empty or brief sensational text)
  ```text
  Local health gurus hate this ancient secret fruit recipe that burns 30 pounds in 48 hours without any exercise!
  ```

### Expected System Behavior
1. **Text Analysis**:
   - High clickbait heuristics triggered by ALL CAPS, exclamation points, and curiosity gap phrases (`YOU WON'T BELIEVE`, `THIS ONE WEIRD TRICK`).
   - Clickbait Score: Very High (>= 75%).
2. **Scoring Rule**: Clickbait threshold (>= 70%) triggers **MISLEADING** verdict even if claims cannot be formally disproven.
3. **Final Verdict**: **MISLEADING** (Clickbait warning highlighted in UI).

---

## 📌 Case 3: Image / Context Mismatch

### Input
- **Headline**: `Massive wildfire sweeps through central Paris causing widespread destruction near Eiffel Tower`
- **Body**:
  ```text
  Emergency services rushed to respond as flames engulfed historic central landmarks during unprecedented heatwaves.
  ```
- **Image**: An image of a quiet snowy winter mountain or an unrelated stock landscape.

### Expected System Behavior
1. **Multimodal Analysis**:
   - Context Match: Low (< 30%).
   - Manipulation / Mismatch Verdict: **Possible Mismatch**.
   - Reasoning notes that the image depicts an unrelated setting (e.g., snowy landscape) contradicting the claimed Parisian wildfire.
2. **Web Verification**: Finds no emergency reports confirming any such catastrophic fire.
3. **Final Verdict**: **FAKE** or **MISLEADING** with the image mismatch badge clearly rendered.

---

## 💡 Troubleshooting & Tips
- If running behind restricted proxies, ensure network access is enabled for DuckDuckGo and Gemini endpoints.
- Keep requests separated by at least 3 seconds to avoid triggering the rate-limit protector.
