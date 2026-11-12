// Camera board selection for the Edge-AI Smart Dustbin.
// Uncomment EXACTLY ONE board. ESP32-S3 boards are recommended: 2-3x faster AI and 8 MB PSRAM.
#pragma once

#define BOARD_ESP32S3_CAM      // ESP32-S3-CAM / Freenove ESP32-S3-WROOM CAM / ESP32-S3-EYE pin layout (recommended)
// #define BOARD_XIAO_ESP32S3  // Seeed Studio XIAO ESP32S3 Sense
// #define BOARD_AI_THINKER    // classic ESP32-CAM (AI-Thinker, OV2640) - works, but slower

#if defined(BOARD_ESP32S3_CAM)
  // Arduino IDE: Board "ESP32S3 Dev Module", PSRAM "OPI PSRAM", Flash 8/16 MB, Partition "Huge APP"
  #define PWDN_GPIO_NUM  -1
  #define RESET_GPIO_NUM -1
  #define XCLK_GPIO_NUM  15
  #define SIOD_GPIO_NUM   4   // camera SDA: never use GPIO 4 for a LED on this board
  #define SIOC_GPIO_NUM   5
  #define Y9_GPIO_NUM    16
  #define Y8_GPIO_NUM    17
  #define Y7_GPIO_NUM    18
  #define Y6_GPIO_NUM    12
  #define Y5_GPIO_NUM    10
  #define Y4_GPIO_NUM     8
  #define Y3_GPIO_NUM     9
  #define Y2_GPIO_NUM    11
  #define VSYNC_GPIO_NUM  6
  #define HREF_GPIO_NUM   7
  #define PCLK_GPIO_NUM  13
  #define LIGHT_GPIO_NUM 47   // MOSFET gate for the white LED ring (no flash LED on this board)
  #define UART_RX_GPIO   14   // <- main ESP32 TX2 (GPIO 17)
  #define UART_TX_GPIO   21   // -> main ESP32 RX2 (GPIO 16)
  #define CAMERA_BOARD_NAME "ESP32-S3-CAM"

#elif defined(BOARD_XIAO_ESP32S3)
  // Arduino IDE: Board "XIAO_ESP32S3", PSRAM "OPI PSRAM"
  #define PWDN_GPIO_NUM  -1
  #define RESET_GPIO_NUM -1
  #define XCLK_GPIO_NUM  10
  #define SIOD_GPIO_NUM  40
  #define SIOC_GPIO_NUM  39
  #define Y9_GPIO_NUM    48
  #define Y8_GPIO_NUM    11
  #define Y7_GPIO_NUM    12
  #define Y6_GPIO_NUM    14
  #define Y5_GPIO_NUM    16
  #define Y4_GPIO_NUM    18
  #define Y3_GPIO_NUM    17
  #define Y2_GPIO_NUM    15
  #define VSYNC_GPIO_NUM 38
  #define HREF_GPIO_NUM  47
  #define PCLK_GPIO_NUM  13
  #define LIGHT_GPIO_NUM  1   // D0: MOSFET gate for the LED ring
  #define UART_RX_GPIO   44   // D7
  #define UART_TX_GPIO   43   // D6
  #define CAMERA_BOARD_NAME "XIAO ESP32S3 Sense"

#elif defined(BOARD_AI_THINKER)
  // Arduino IDE: Board "AI Thinker ESP32-CAM", PSRAM "Enabled", Partition "Huge APP"
  #define PWDN_GPIO_NUM  32
  #define RESET_GPIO_NUM -1
  #define XCLK_GPIO_NUM   0
  #define SIOD_GPIO_NUM  26
  #define SIOC_GPIO_NUM  27
  #define Y9_GPIO_NUM    35
  #define Y8_GPIO_NUM    34
  #define Y7_GPIO_NUM    39
  #define Y6_GPIO_NUM    36
  #define Y5_GPIO_NUM    21
  #define Y4_GPIO_NUM    19
  #define Y3_GPIO_NUM    18
  #define Y2_GPIO_NUM     5
  #define VSYNC_GPIO_NUM 25
  #define HREF_GPIO_NUM  23
  #define PCLK_GPIO_NUM  22
  #define LIGHT_GPIO_NUM  4   // on-board flash LED
  #define UART_RX_GPIO   13
  #define UART_TX_GPIO   14
  #define CAMERA_BOARD_NAME "AI-Thinker ESP32-CAM"

#else
  #error "Select a camera board at the top of camera_pins.h"
#endif
