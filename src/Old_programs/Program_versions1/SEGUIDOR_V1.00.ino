#include <HCSR04.h>
HCSR04 hc(2, new int[3]{3, 4, 5}, 3); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo SERVOdrive;
Servo SERVOsteering;

int i=0;
int dir=88;
int di=15;

void setup()
{ Serial.begin(9600);
pinMode (12, INPUT);
pinMode (13, OUTPUT);

SERVOdrive.attach(6);  // 0 AVANZA   90 STOP    180 RETROCEDE
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
   
di=hc.dist(2);
delay(100);

dir=(88+3*(-15+di)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección
if (dir<44) {dir=45;}
if (dir>136) {dir=135;}
delay(2);
SERVOsteering.write(dir);
/*Serial.print("dist=");
Serial.print(di);
Serial.print("    dir=");
Serial.println(dir);*/

}