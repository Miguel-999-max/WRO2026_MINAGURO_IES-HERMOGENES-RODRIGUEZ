// gira por pared interior.
#include <HCSR04.h>
HCSR04 hc(2, new int[4]{3, 4, 5,7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo SERVOdrive;
Servo SERVOsteering;
Servo SERVOcam;
int i=0;
int dir=80;     
int distDE=15;  // SENSOR 0 derecho
int distFR=110; // SENSOR 1 frontal
int distIZ=15;  // SENSOR 2 izquierdo
int distTR=15;  // SENSOR 3 trasero

void setup()
{ Serial.begin(9600);
pinMode (12, INPUT);
pinMode (13, OUTPUT);

SERVOdrive.attach(6);  // 180 AVANZA   90 STOP    0 RETROCEDE
SERVOsteering.attach(9);  // 40 DCHA   80 RECTO   120 IZDA 
SERVOcam.attach(10);      // 0 DCHA   90 RECTO   180 IZDA 
SERVOdrive.write(90);
SERVOsteering.write(dir);
SERVOcam.write(90);

while (digitalRead(12) == LOW) {
    digitalWrite(13, HIGH);
    delay(100);
    digitalWrite(13, LOW);
    delay(100);
  }
  
 }

void giroCCW(){}



void loop()
{
    SERVOdrive.write(0); 
   SERVOsteering.write(dir);

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
    SERVOsteering.write(dir);// 40 DCHA   80 RECTO   120 IZDA 
    distFR=hc.dist(2);// SENSOR 2 izquierdo
    delay(30);}
    }

dir = constrain(dir, 60, 100);// 40 DCHA   80 RECTO   120 IZDA 

SERVOsteering.write(dir);// 40 DCHA   80 RECTO   120 IZDA 
/*
Serial.print("dist=");
Serial.print(distIZ);
Serial.print("    dir=");
Serial.println(dir);*/
}