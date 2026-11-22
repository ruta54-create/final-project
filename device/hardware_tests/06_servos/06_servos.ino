/*
 * TEST 06 - tray + lid servos and finding the right angles (main ESP32 DevKit)
 * Library: ESP32Servo
 * Wiring: servo signal (orange/yellow) -> GPIO27 (tray) and GPIO14 (lid)
 *         servo red  -> +5V of the EXTERNAL 5V adapter (never the ESP32 5V pin)
 *         servo brown -> GND of the adapter AND GND of the ESP32 (common ground)
 *         1000 uF capacitor across the adapter's +5V and GND (long leg / + to +5V)
 * Use: Serial Monitor at 115200, "Newline" line ending. Type commands:
 *   t90   -> tray to 90 degrees     l0  -> lid to 0 degrees
 *   demo  -> runs the same movements as the real firmware
 * Write down the tray angles for "flat", "drop left (organic)", "drop right (inorganic)" and the lid angles
 * for "closed" / "open", then copy them into esp32_main.ino (TRAY_CENTER, TRAY_ORGANIC, ...).
 */
#include <ESP32Servo.h>
Servo tray, lid;
const int TRAY_CENTER = 90, TRAY_ORGANIC = 30, TRAY_INORGANIC = 150, LID_CLOSED = 0, LID_OPEN = 100;

void setup() {
  Serial.begin(115200);
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  tray.setPeriodHertz(50); tray.attach(27, 500, 2400);
  lid.setPeriodHertz(50);  lid.attach(14, 500, 2400);
  tray.write(TRAY_CENTER); lid.write(LID_CLOSED);
  Serial.println("TEST 06: servos. Commands: t<angle>, l<angle>, demo");
}

void loop() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n'); cmd.trim();
  if (cmd == "demo") {
    Serial.println("lid open");  lid.write(LID_OPEN);  delay(1500);
    Serial.println("lid close"); lid.write(LID_CLOSED); delay(1500);
    Serial.println("tray organic");   tray.write(TRAY_ORGANIC);   delay(1200); tray.write(TRAY_CENTER); delay(800);
    Serial.println("tray inorganic"); tray.write(TRAY_INORGANIC); delay(1200); tray.write(TRAY_CENTER);
  } else if (cmd.length() > 1 && (cmd[0] == 't' || cmd[0] == 'l')) {
    int a = constrain(cmd.substring(1).toInt(), 0, 180);
    (cmd[0] == 't' ? tray : lid).write(a);
    Serial.printf("%s -> %d degrees\n", cmd[0] == 't' ? "tray" : "lid", a);
  }
}
