#include <SPI.h>
#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();

const int toggleBtn = 5;

int x = 10;
int y = 30;
int checkStatus = 1;
int lastButtonState = HIGH;
uint8_t smallTextSize = 1;
uint8_t largeTextSize = 2;
unsigned long idleTimeout = 5000;
unsigned long lastUpdate = 0;
unsigned long lastDebounceMs = 0;
const unsigned long debounceDelay = 200;

uint16_t COLOR_BROWN, COLOR_ORANGE;

void drawCentered(const String& str, int32_t y, uint16_t fgcolor, uint16_t bgcolor = TFT_WHITE, uint8_t textSize = largeTextSize){
  tft.setTextSize(textSize);
  tft.setTextColor(fgcolor, bgcolor);
  if (textSize == largeTextSize) { // draw texts
    tft.drawString(str, (tft.width() / 2) - str.length() * 8, y);
  } else { // draw token
    tft.drawString(str, (tft.width() / 2) - str.length() * 5, y);
  }
}

void drawStatus(int status) {
  const int cx = tft.width() / 2;
  const int cy = tft.height() / 2 + 10;
  tft.fillRect(0, 70, tft.width(), tft.height() - 120, TFT_WHITE);
  // draw checkout door
  if (status == 0) {
    int w = 120, h = 140;
    int rx = cx - w / 2;
    int ry = cy - h / 2;
    tft.fillRect(rx, ry, w, h, COLOR_BROWN);
    tft.drawRect(rx, ry, w, h, TFT_BLACK);
    tft.fillCircle(rx + w - 20, ry + h / 2, 6, TFT_YELLOW);
    tft.drawCircle(rx + w - 20, ry + h / 2, 6, TFT_BLACK);
    drawCentered("Checked out", tft.height() - 40, TFT_BLACK);
  } else if (status == 1) {
    // draw checkin
    tft.fillCircle(cx, cy, 50, TFT_GREEN);
    tft.drawLine(cx - 20, cy,      cx - 5,  cy + 20, TFT_WHITE);
    tft.drawLine(cx - 5,  cy + 20, cx + 25, cy - 25, TFT_WHITE);
    drawCentered("Checked in", tft.height() - 40, TFT_BLACK);
  } else {
    tft.fillCircle(cx, cy, 50, TFT_BLUE);
    tft.fillCircle(cx - 20, cy, 8, TFT_WHITE);
    tft.fillCircle(cx,      cy, 8, TFT_WHITE);
    tft.fillCircle(cx + 20, cy, 8, TFT_WHITE);

    drawCentered("Wait", tft.height() - 40, TFT_BLACK);
  }
}

void printData(String data) {
  tft.fillScreen(TFT_WHITE);
  int start = 0;
  int dividerIndex;
  int fieldIndex = 0;
  String token;

  while ((dividerIndex = data.indexOf(',', start)) != -1) {
    String message = data.substring(start, dividerIndex);
    if (fieldIndex == 0) {
      token = message;
    } else if (fieldIndex == 1) {
      drawStatus(message.toInt());
    } else {
      if (message.length()) {
        drawCentered(message, 20, TFT_BLACK, TFT_WHITE, smallTextSize);
        Serial.println(message);
      }
    }
    start = dividerIndex + 1;
    fieldIndex++;
  }
  String message = data.substring(start);
  if (message.length()) {
    if (fieldIndex == 0) {
      token = message;
    } else if (fieldIndex == 1) {
      drawStatus(message.toInt());
    } else {
      drawCentered(message, 20, TFT_BLACK, TFT_WHITE, smallTextSize);
      Serial.println(message);
    }
    fieldIndex++;
  }
}


void setup() {
  pinMode(toggleBtn, INPUT_PULLUP);
  Serial.begin(115200);
  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_WHITE);
  tft.setFreeFont(&FreeSans9pt7b);
  tft.setTextColor(TFT_GREEN, TFT_WHITE);
  drawCentered("Idle", 20, TFT_BLACK);
  lastUpdate = millis();
  COLOR_BROWN  = tft.color565(165, 42, 42);
  COLOR_ORANGE = tft.color565(255, 165, 0);
  drawCentered("---", tft.height() - 40, TFT_BLUE);
}

void loop() {
  tft.setTextSize(largeTextSize);
  int reading = digitalRead(toggleBtn);
  if (reading != lastButtonState) {
    lastDebounceMs = millis();

  }
  if ((millis() - lastDebounceMs) > debounceDelay) {
    static int stableState = HIGH;
    if (reading != stableState) {
      if (reading == HIGH && stableState == LOW) {
        checkStatus = 1 - checkStatus;
        tft.fillScreen(TFT_WHITE);
        drawCentered("Mode toggled", 20, TFT_BLUE);
        drawStatus(checkStatus);
        Serial.printf("MODE:%d\n", checkStatus);
        lastUpdate = millis();
      }
      stableState = reading;
    }
  }
  lastButtonState = reading;

  if (Serial.available()) {
    String serialInput = Serial.readStringUntil('\n');
    serialInput.trim();
    printData(serialInput);
    lastUpdate = millis();
  }
  if (millis() - lastUpdate > idleTimeout) {
    tft.fillScreen(TFT_WHITE);
    drawCentered("Idle", 20, TFT_BLACK);
    drawCentered("---", tft.height() - 40, TFT_BLUE);
    lastUpdate = millis();
  }
}