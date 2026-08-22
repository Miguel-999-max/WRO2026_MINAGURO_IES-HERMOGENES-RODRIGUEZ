// 
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_HMC5883_U.h>

/* Asignar un ID único al sensor */
Adafruit_HMC5883_Unified mag = Adafruit_HMC5883_Unified(12345);


#include <HCSR04.h>
HCSR04 hc(2, new int[4]{3, 4, 5, 7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo servoTraccion;
Servo servoDireccion;
Servo SERVOcam;
int i=0;
int dir=80;     
int distDE=15;  // SENSOR 0 derecho
int distFR=110; // SENSOR 1 frontal
int distIZ=15;  // SENSOR 2 izquierdo
int distTR=15;  // SENSOR 3 trasero
int Izda=120;
int Dcha=60;
int Recto=87;
int Para=90;
int Avanza=0;
int Retrocede=180;
int offsetX=0;
int offsetY=0;

void setup()
{ Serial.begin(9600);
pinMode (12, INPUT);
pinMode (13, OUTPUT);

mag.begin();

servoTraccion.attach(6);  // 0 AVANZA   90 STOP    180 RETROCEDE
servoDireccion.attach(9);  // 52 DCHA   87 RECTO   122 IZDA 
SERVOcam.attach(10);      // 0 DCHA   90 RECTO   180 IZDA 
servoTraccion.write(Para);
servoDireccion.write(Recto);
SERVOcam.write(90);

while (digitalRead(12) == LOW) {
    digitalWrite(13, HIGH);
    delay(100);
    digitalWrite(13, LOW);
    delay(100);
  }
  
 }

void desaparcaIzda(){
distTR = hc.dist(3);
  delay(50);
    
    if (distTR > 6) {
        servoTraccion.write(Retrocede);
    }
    else {
          servoTraccion.write(Para);
          delay(1000);}

if (distTR < 7) {
        girar90Izquierda();
    }
}

void girar90Izquierda() {

  sensors_event_t event;
  mag.getEvent(&event);
  float rumboAntesDeGirar = atan2(event.magnetic.y, event.magnetic.x) * 180 / PI;
  if (rumboAntesDeGirar < 0) rumboAntesDeGirar += 360; 

  float rumboDeseado = rumboAntesDeGirar - 90;
  if (rumboDeseado < 0) rumboDeseado += 360; 


  float error = 90; // 90 es lo que queremos girar

  while (abs(error) > 3) { 
    mag.getEvent(&event);
    float actual = atan2(event.magnetic.y, event.magnetic.x) * 180 / PI;
    if (actual < 0) actual += 360;

    error = rumboDeseado - actual;
    
    if (error > 180) error -= 360;
    if (error < -180) error += 360;

    servoDireccion.write(Izda); 
    servoTraccion.write(80);
  }

  // 5. FINALIZAR
  servoDireccion.write(Recto); 
  servoTraccion.write(Para);
}


void giroCCW(){
 servoTraccion.write(0); 
   servoDireccion.write(dir);

distIZ=hc.dist(2);// SENSOR 2 izquierdo
delay(30);
distFR=hc.dist(1);// SENSOR 1 frontal
delay(30);

if (distFR>20)
{
dir=(80+3*(-15+distIZ)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección
}

else {
  while (distIZ>15)
    {dir=60;
    servoDireccion.write(dir);
    distFR=hc.dist(2);// SENSOR 2 izquierdo
    delay(30);}
    }

dir = constrain(dir, 60, 100);// 40 DCHA   80 RECTO   120 IZDA 

servoDireccion.write(dir);// 40 DCHA   80 RECTO   120 IZDA 
/*
Serial.print("dist=");
Serial.print(distIZ);
Serial.print("    dir=");
Serial.println(dir);*/
}



void loop()
{
  desaparcaIzda();

}