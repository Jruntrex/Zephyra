#include <Wire.h>
#include <Adafruit_PN532.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h> // Потрібно встановити через Library Manager

// --- ПІНИ ---
#define I2C_SDA 8
#define I2C_SCL 9
#define LED_PIN 10
#define BUZZ_PIN 7

// --- НАЛАШТУВАННЯ МЕРЕЖІ ТА СЕРВЕРА ---
const char* WIFI_SSID     = "TP-Link_C4BE";
const char* WIFI_PASSWORD = "49909210";
const char* SERVER_IP   = "192.168.0.111";
const int   SERVER_PORT = 8000;
const char* ENDPOINT    = "/api/rfid/scan/";

Adafruit_PN532 nfc(I2C_SDA, I2C_SCL);

// --- ФУНКЦІЇ СИГНАЛІВ ---

// Короткі піки (для успіху)
void beepSuccess(int count) {
  for (int i = 0; i < count; i++) {
    digitalWrite(LED_PIN, HIGH);
    digitalWrite(BUZZ_PIN, HIGH);
    delay(120);
    digitalWrite(LED_PIN, LOW);
    digitalWrite(BUZZ_PIN, LOW);
    if (i < count - 1) delay(120); 
  }
}

// Один довгий сигнал (для помилки)
void beepError() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(BUZZ_PIN, HIGH);
  delay(1000); 
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZ_PIN, LOW);
}

void connectWiFi() {
  Serial.printf("\nСпроба підключення до %s", WIFI_SSID);
  
  // Повністю скидаємо попередні налаштування для уникнення помилки "cannot set config"
  WiFi.disconnect(true); 
  delay(1000);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi OK — IP: %s\n", WiFi.localIP().toString().c_str());
    beepSuccess(3);
  } else {
    Serial.println("\nПомилка: не вдалося підключитися. Перевірте пароль або сигнал.");
    beepError();
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZ_PIN, OUTPUT);

  connectWiFi();

  nfc.begin();
  if (!nfc.getFirmwareVersion()) {
    Serial.println("PN532 не знайдено!");
    while (1) beepError(); 
  }

  nfc.SAMConfig();
  Serial.println("--- СИСТЕМА ГОТОВА ---");
}

void loop() {
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;

  // Очікування картки
  if (!nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 500)) return;

  // Формуємо UID як рядок
  String uidStr = "";
  for (uint8_t i = 0; i < uidLength; i++) {
    if (i > 0) uidStr += ":";
    if (uid[i] < 0x10) uidStr += "0";
    uidStr += String(uid[i], HEX);
  }
  uidStr.toUpperCase();
  Serial.printf("\nЗчитано UID: %s\n", uidStr.c_str());

  // Короткий "відгук" на зчитування (одразу)
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(BUZZ_PIN, HIGH);
  delay(80);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZ_PIN, LOW);

  // Відправка на сервер
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + ENDPOINT;
    
    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    String jsonBody = "{\"uid\":\"" + uidStr + "\"}";
    int httpResponseCode = http.POST(jsonBody);

    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.printf("Статус: %d. Відповідь: %s\n", httpResponseCode, response.c_str());

      // Парсимо відповідь, щоб зрозуміти напрямок (in/out)
      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, response);

      if (!error) {
        String direction = doc["direction"]; // Припускаємо, що Django повертає {"direction": "in"}
        
        if (direction == "in") {
          delay(100);
          beepSuccess(1); // ОДИН РАЗ — ВХІД
        } else if (direction == "out") {
          delay(100);
          beepSuccess(2); // ДВА РАЗИ — ВИХІД
        } else {
          beepSuccess(1); // Дефолт
        }
      } else {
        // Якщо JSON не розпарсився, але код 200 — просто пікаємо 1 раз
        beepSuccess(1);
      }
    } else {
      Serial.printf("Помилка запиту: %s\n", http.errorToString(httpResponseCode).c_str());
      beepError(); // ДОВГИЙ СИГНАЛ — ПОМИЛКА З'ЄДНАННЯ
    }
    http.end();
  } else {
    connectWiFi();
  }

  delay(2000); // Анти-дребезг (пауза перед наступною картою)
}