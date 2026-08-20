#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_HMC5883_U.h>

/* Asignar un ID único al sensor */
Adafruit_HMC5883_Unified mag = Adafruit_HMC5883_Unified(12345);

void setup() {
  Serial.begin(9600);
  Serial.println("Prueba del Magnetómetro HMC5883L");
  
  /* Inicializar el sensor */
  if(!mag.begin()) {
    /* Si hay un problema, avisar */
    Serial.println("No se detectó el HMC5883L... ¡revisa el cableado!");
    while(1);
  }
}

void loop() {
 float xMax = -999, xMin = 999, yMax = -999, yMin = 999;
  Serial.println("Gira el robot 360 grados lentamente...");

  for (int i = 0; i < 5000; i++) { // Tienes unos 10 segundos para girarlo
    sensors_event_t event;
    mag.getEvent(&event);

    if (event.magnetic.x < xMin) xMin = event.magnetic.x;
    if (event.magnetic.x > xMax) xMax = event.magnetic.x;
    if (event.magnetic.y < yMin) yMin = event.magnetic.y;
    if (event.magnetic.y > yMax) yMax = event.magnetic.y;
    delay(10);
  }

  float offsetX = (xMax + xMin) / 2;
  float offsetY = (yMax + yMin) / 2;

  Serial.print("OffsetX: "); Serial.println(offsetX);
  Serial.print("OffsetY: "); Serial.println(offsetY);
  
  /*Si obtienes esos valores de Offset, solo tienes que restarlos en tu cálculo del rumbo:
float actual = atan2(event.magnetic.y - offsetY, event.magnetic.x - offsetX) * 180 / PI;*/
}
