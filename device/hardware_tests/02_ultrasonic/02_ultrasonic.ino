/*
 * TEST 02 - the 3 HC-SR04 ultrasonic sensors (main ESP32 DevKit)
 * Wiring (each sensor): VCC -> 5V, GND -> GND, TRIG -> ESP32 pin,
 *   ECHO -> 1k resistor -> ESP32 pin, and ESP32 pin -> 2k resistor -> GND  (5V echo -> 3.3V)
 *   organic   TRIG 5   ECHO 18
 *   inorganic TRIG 19  ECHO 21
 *   hand      TRIG 22  ECHO 23
 * Expected: three distances in cm every second. Move your hand in front of each sensor:
 * the number must change. "--" means no echo (check wiring / divider / sensor facing a wall < 2 cm).
 */
const int TRIG[3] = {5, 19, 22};
const int ECHO[3] = {18, 21, 23};
const char* NAME[3] = {"organic", "inorganic", "hand"};

float readCm(int trig, int echo) {
  digitalWrite(trig, LOW);  delayMicroseconds(3);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, 30000);
  return us == 0 ? -1 : us * 0.0343f / 2.0f;     // speed of sound 343 m/s, there and back
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) { pinMode(TRIG[i], OUTPUT); pinMode(ECHO[i], INPUT); }
  Serial.println("TEST 02: ultrasonic sensors");
}

void loop() {
  for (int i = 0; i < 3; i++) {
    float d = readCm(TRIG[i], ECHO[i]);
    if (d < 0) Serial.printf("%-10s --      ", NAME[i]);
    else       Serial.printf("%-10s %5.1f cm ", NAME[i], d);
    delay(60);                                    // let echoes die before the next sensor
  }
  Serial.println();
  delay(1000);
}
