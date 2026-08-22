#include <Wire.h>
#include <LSM303.h>// 0x1E: Es el Magnetómetro (brújula) del LSM303DLHC.
                    //0x19: Es el Acelerómetro del LSM303DLHC.
                    //0x69: Es el Giroscopio (probablemente un L3GD20 o similar, que suele acompañar al LSM303 en los módulos 10 DOF).
LSM303 compass;

void setup() {
  Serial.begin(115200);
  while (!Serial); // Espera al monitor serie de la R4

  Wire.begin();

  Serial.println("Iniciando LSM303DLHC...");

  // Forzamos la inicialización
  if (!compass.init()) {
    Serial.println("Fallo al detectar el sensor por software");
    while (1);
  }
  
  compass.enableDefault();
  
  // Calibración básica: Estos valores son genéricos. 
  // Sin esto, el cálculo de 'heading' puede dar 0 o error.
  compass.m_min = (LSM303::vector<int16_t>){-32767, -32767, -32767};
  compass.m_max = (LSM303::vector<int16_t>){+32767, +32767, +32767};

  Serial.println("Sensor listo. Mueve el modulo...");
}

void loop() {
  compass.read();

  // Leemos los ejes X, Y, Z del magnetómetro directamente
  float heading = compass.heading();

  Serial.print("M: ");
  Serial.print(compass.m.x); Serial.print(", ");
  Serial.print(compass.m.y); Serial.print(", ");
  Serial.print(compass.m.z);
  Serial.print(" | Rumbo: ");
  Serial.println(heading);

  delay(500);
}
