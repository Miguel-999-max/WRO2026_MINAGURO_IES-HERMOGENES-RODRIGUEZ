// POTENCIOMETRO CON 1 SERVO

#include <Servo.h>
Servo SERVOx;

int JOYx = A0;   //LECTURA:   0--508-1023

int Sx=0;


void setup() {

SERVOx.attach(9);  // vincula el servo al pin digital 6


Serial.begin(9600);

  }

void loop(){
  JOYx = analogRead(A0);
  
Sx = map(JOYx, 0, 1023, 55, 125); //map(value, fromLow, fromHigh, toLow, toHigh) 360º 60(dcha)-120(izda)


SERVOx.write(Sx);


Serial.print("JOYx=");
Serial.print(JOYx);


Serial.print("  Sx= ");
Serial.println(Sx);

delay(100);
}
