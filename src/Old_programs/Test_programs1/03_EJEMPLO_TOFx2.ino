#include "Adafruit_VL53L0X.h"   //A4 SDA
                                //A5 SCL

// Definir pines XSHUT
#define SHT_LOX1 4
#define SHT_LOX2 5

// Direcciones I2C personalizadas (la default es 0x29)
#define ADDR1 0x30
#define ADDR2 0x31

// Crear los objetos de los sensores
Adafruit_VL53L0X lox1 = Adafruit_VL53L0X();
Adafruit_VL53L0X lox2 = Adafruit_VL53L0X();

void setup() {
  Serial.begin(115200);

  // Configurar pines XSHUT como salida
  pinMode(SHT_LOX1, OUTPUT);
  pinMode(SHT_LOX2, OUTPUT);

  // 1. Apagar ambos sensores (RESET)
  digitalWrite(SHT_LOX1, LOW);
  digitalWrite(SHT_LOX2, LOW);
  delay(10);

  // 2. Activar e inicializar Sensor 1
  pinMode(SHT_LOX1, INPUT);
  delay(100);
  if(!lox1.begin(ADDR1)) {
    Serial.println(F("Error al iniciar Sensor 1"));
    while(1);
  }

  // 3. Activar e inicializar Sensor 2
  pinMode(SHT_LOX2, INPUT);
  delay(100);
  if(!lox2.begin(ADDR2)) {
    Serial.println(F("Error al iniciar Sensor 2"));
    while(1);
  }

  Serial.println(F("Sensores listos!"));
}

void loop() {
  VL53L0X_RangingMeasurementData_t measure1;
  VL53L0X_RangingMeasurementData_t measure2;

  lox1.rangingTest(&measure1, false);
  lox2.rangingTest(&measure2, false);

  // Imprimir lecturas del Sensor 1
  Serial.print("S1: ");
  if (measure1.RangeStatus != 4) Serial.print(measure1.RangeMilliMeter);
  else Serial.print("Fuera de rango");

  // Imprimir lecturas del Sensor 2
  Serial.print(" mm | S2: ");
  if (measure2.RangeStatus != 4) Serial.print(measure2.RangeMilliMeter);
  else Serial.print("Fuera de rango");

  Serial.println(" mm");
  delay(100);
}
