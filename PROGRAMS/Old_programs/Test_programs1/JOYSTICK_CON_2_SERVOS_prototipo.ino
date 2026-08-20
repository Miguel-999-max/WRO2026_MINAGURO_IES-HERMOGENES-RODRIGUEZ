// Montaje 11: JOYSTICK CON 2 SERVOS

#include <Servo.h>
Servo SERVOx;
Servo SERVOy;

int JOYx = A0;   //LECTURA:   0--508-1023
int JOYy = A1;   //LECTURA:   0--508-1023
int Sx=0;
int Sy=0;

void setup() {

SERVOx.attach(6);  // tracción
SERVOy.attach(9);  // dirección
Serial.begin(9600);

  }

void loop(){
  JOYx = analogRead(A0);
  JOYy = analogRead(A1);

Sx = map(JOYx, 0, 1023, 0, 180); //map(value, fromLow, fromHigh, toLow, toHigh) delante-detras

Sy = map(JOYy, 0, 1023, 50, 130); //dirección

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
