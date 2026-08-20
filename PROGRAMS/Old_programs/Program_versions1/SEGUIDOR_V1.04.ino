#include <HCSR04.h>
HCSR04 hc(2, new int[3]{3, 4, 5}, 3); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo SERVOdrive;
Servo SERVOsteering;

int i=0;
int dir=88;
int dist=15;
int avanza=110;

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
  SERVOdrive.write(avanza); 
  

  float lecturaActual = hc.dist(2);

  if (lecturaActual > 0 && lecturaActual < 200) {
      dist = (dist * 0.7) + (lecturaActual * 0.3); 
  }

  int error = dist - 15;

  // Si el error es menor a 1 cm, no corregimos (mantiene dir=88)
  if (abs(error) <= 1) {
    dir = 88;
  } else {
    dir = 88 + (2 * error); 
  }

  dir = constrain(dir, 50, 130);

  SERVOsteering.write(dir);
  
  delay(50); 
}