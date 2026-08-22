#include <HCSR04.h>
HCSR04 hc(2, new int[3]{3, 4, 5}, 3); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo SERVOdrive;
Servo SERVOsteering;

int i=0;
int dir=80;
int dist=15;

void setup()
{ Serial.begin(9600);
pinMode (12, INPUT);
pinMode (13, OUTPUT);

SERVOdrive.attach(6);  // 180 AVANZA   90 STOP    0 RETROCEDE
SERVOsteering.attach(9);  // 45 DCHA   88 RECTO   135 IZDA 
SERVOdrive.write(90);
SERVOsteering.write(dir);

while (digitalRead(12) == LOW) {
    digitalWrite(13, HIGH);
    delay(100);
    digitalWrite(13, LOW);
    delay(100);
  }
 }

void loop()
{
   SERVOdrive.write(0); 
   SERVOsteering.write(dir);
dist=hc.dist(2);
delay(30);

dir=(80+3*(-15+dist)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección

dir = constrain(dir, 60, 100);

SERVOsteering.write(dir);

Serial.print("dist=");
Serial.print(dist);
Serial.print("    dir=");
Serial.println(dir);
}