/*
 * TEST 07 (part A) - UART link, upload this to the MAIN ESP32 DevKit.
 * Upload 07_uart_cam to the camera board at the same time.
 * Wiring:  main GPIO17 (TX2) -> camera GPIO14 (its RX)
 *          main GPIO16 (RX2) <- camera GPIO21 (its TX)
 *          main GND          -- camera GND   (without a common ground the bytes are garbage)
 * Expected in the main board's Serial Monitor every 3 s:  camera says: SORT organic 0.990
 */
HardwareSerial CamSerial(2);

void setup() {
  Serial.begin(115200);
  CamSerial.begin(115200, SERIAL_8N1, 16, 17);   // RX = 16, TX = 17
  Serial.println("TEST 07: UART link (main side)");
}

void loop() {
  while (CamSerial.available()) CamSerial.read();
  CamSerial.print("CAPTURE\n");
  String line;
  unsigned long t = millis();
  bool got = false;
  while (millis() - t < 3000 && !got) {
    if (CamSerial.available()) {
      char c = CamSerial.read();
      if (c == '\n') got = true; else line += c;
    }
  }
  if (got) Serial.println("camera says: " + line);
  else Serial.println("no answer: check TX->RX crossing, common GND, both boards powered");
  delay(3000);
}
