
#include <HCSR04.h>
HCSR04 hc(2, new int[4]{3, 4, 5, 7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo servoTraccion;
Servo servoDireccion;
Servo SERVOcam;

int i=0;
int dir=90;     
int distDE=15;  // SENSOR 0 derecho
int distFR=110; // SENSOR 1 frontal
int distIZ=15;  // SENSOR 2 izquierdo
int distTR=15;  // SENSOR 3 trasero

// Variables control servos
int Izda=130;
int Dcha=50;
int Recto=90;
int Para=90;
int Avanza=0;
int Retrocede=180;
int lectura=0;
int CASO;

void setup()
{ //Serial.begin(9600);
pinMode (12, INPUT);
pinMode (13, OUTPUT);

servoTraccion.attach(6);  // 0 AVANZA   90 STOP    180 RETROCEDE
servoDireccion.attach(9);  // 40 DCHA   80 RECTO   120 IZDA 
SERVOcam.attach(10);      // 0 DCHA   90 RECTO   180 IZDA 
servoTraccion.write(90);
servoDireccion.write(dir);
SERVOcam.write(90);

while (digitalRead(12) == LOW) {
    digitalWrite(13, HIGH);
    delay(100);
    digitalWrite(13, LOW);
    delay(100);
  }
  
 }

void scanINIT(){
  while (true){
distDE=hc.dist(0);
delay(60);
distIZ=hc.dist(2);
delay(60);
if ((distDE>2)&&(distDE<90)&&(distIZ>2)&&(distIZ<90))
    {break;}
}

if (distDE > distIZ) {
   CASO=1;
   desaparcaCW();
   } //CW a izquierdas

if (distDE < distIZ) {
   CASO=0;
   desaparcaCCW();
   } //CWW a derechas
}



void desaparcaCW(){
  


//giroCW();
}


void desaparcaCCW(){

int di = hc.dist(3);
int di2 = hc.dist(1);
  delay(50);
    
    if (di > 6) {
          servoTraccion.write(Retrocede);
    }
      else {

          servoTraccion.write(Para);
          delay(500);
          servoTraccion.write(80);
          servoDireccion.write(110);
          delay(9000);

          servoTraccion.write(Para);
          delay(6000);

          servoTraccion.write(70);
          servoDireccion.write(80);
          delay(3000);

       giroCCW();
      }
}


void giroCCW(){

while(true) {
servoTraccion.write(0); 
   servoDireccion.write(dir);
distIZ=hc.dist(2);
delay(30);

dir=(80+3*(-15+distIZ)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección

dir = constrain(dir, 50, 130);

servoDireccion.write(dir);
    }
}


void loop() {

desaparcaCCW();




}