/*
 * TEST 07 (part B) - UART link, upload this to the CAMERA board (ESP32-S3-CAM).
 * It pretends to be the AI: answers every "CAPTURE" with a fixed result.
 * Pins for ESP32-S3-CAM: RX 14, TX 21 (other boards: see device/esp32_cam/camera_pins.h)
 * Expected in the camera's Serial Monitor: "got CAPTURE" every 3 s.
 */
HardwareSerial MainSerial(1);
const int UART_RX = 14, UART_TX = 21;

void setup() {
  Serial.begin(115200);
  MainSerial.begin(115200, SERIAL_8N1, UART_RX, UART_TX);
  Serial.println("TEST 07: UART link (camera side)");
}

void loop() {
  static String line;
  while (MainSerial.available()) {
    char c = MainSerial.read();
    if (c == '\n') {
      line.trim();
      Serial.println("got " + line);
      if (line == "CAPTURE") MainSerial.print("SORT organic 0.990\n");
      line = "";
    } else if (line.length() < 32) {
      line += c;
    }
  }
}
