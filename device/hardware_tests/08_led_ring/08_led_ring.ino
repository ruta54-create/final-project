/*
 * TEST 08 - white LED ring through the MOSFET (camera board, ESP32-S3-CAM)
 * Wiring: GPIO47 -> 220R -> IRLZ44N GATE;  GATE -> 10k -> GND (keeps the light OFF while booting)
 *         IRLZ44N SOURCE -> GND;  DRAIN -> LED ring (-);  LED ring (+) -> +5V
 * Expected: the ring is ON 1 s, OFF 1 s.
 */
const int LIGHT = 47;

void setup() {
  Serial.begin(115200);
  pinMode(LIGHT, OUTPUT);
  Serial.println("TEST 08: LED ring");
}

void loop() {
  Serial.println("light ON");  digitalWrite(LIGHT, HIGH); delay(1000);
  Serial.println("light OFF"); digitalWrite(LIGHT, LOW);  delay(1000);
}
