//Program to calibrate the steering servo.

#include <Servo.h>
Servo SERVOx;
Servo SERVOy;

int JOYx = A0;   //LECTURA:   0--508-1023
int JOYy = A1;   //LECTURA:   0--508-1023
int Sx=0;
int Sy=0;

void setup() {

SERVOx.attach(6);  // vincula el servo al pin digital 6
SERVOy.attach(9);  // vincula el servo al pin digital 9  

Serial.begin(9600);

  }

void loop(){
  JOYx = analogRead(A0);
  JOYy = analogRead(A1);

Sx = map(JOYx, 0, 1023, 0, 180); //map(value, fromLow, fromHigh, toLow, toHigh)
Sy = map(JOYy, 0, 1023, 0, 180);

SERVOx.write(Sx);
SERVOy.write(Sy);

/*Serial.print("JOYx=");
Serial.print(JOYx);
Serial.print("  JOYy=");
Serial.print(JOYy);
Serial.print("  Sx= ");
Serial.print(Sx);
Serial.print("  Sy= ");
Serial.println(Sy);*/
delay(10);
}
