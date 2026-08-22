#include <HCSR04.h>

HCSR04 hc(2, new int[4]{3, 4, 5, 7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)
int i=0;


void setup()
{ Serial.begin(9600);
pinMode (12, INPUT);
pinMode (13, OUTPUT);

while (digitalRead(12) == LOW) {
    digitalWrite(13, HIGH);
    delay(200);
    digitalWrite(13, LOW);
    delay(200);
  }
 }

void loop()
{
    for (int i = 0; i < 4; i++ )
       { Serial.print("medidor ");
        Serial.print(i);
        Serial.print(" =");
        Serial.println( hc.dist(i) ); //return curent distance (cm) in serial for sensor 1 to 6
        delay(60);  }                      // we suggest to use over 60ms measurement cycle, in order to prevent trigger signal to the echo signal.
Serial.println("-----------");
delay(2000);
}