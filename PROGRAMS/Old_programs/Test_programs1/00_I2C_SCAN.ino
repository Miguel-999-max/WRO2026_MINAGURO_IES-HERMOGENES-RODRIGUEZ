#include <Wire.h>
void setup() {
  Wire.begin();
  Serial.begin(115200);
  Serial.println("\nEscaneando I2C...");
}
void loop() {
  byte error, address;
  int nDevices = 0;
  for(address = 1; address < 127; address++ ) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("Dispositivo encontrado en: 0x");
      if (address<16) Serial.print("0");
      Serial.println(address,HEX);
      nDevices++;
    }
  }
  if (nDevices == 0) Serial.println("No se encontraron dispositivos I2C\n");
  delay(5000);
}