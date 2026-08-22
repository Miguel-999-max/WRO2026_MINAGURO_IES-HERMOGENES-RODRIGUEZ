
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
servoDireccion.attach(9);  // 50 DCHA   90 RECTO   130 IZDA 
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

void scan1(){
  while (true){
distFR=hc.dist(1);
delay(60);
if ((distFR>2)&&(distFR<250))
    {break;}
}

if (distFR > 40) {
   CASO=1;  //El robot esta en la zona de salida
   scanABIERTO();
   } 

if (distDE < 40) {
   CASO=2;   //El robot esta en el aparcamiento
   scanOBSTACULOS();
   } 
}

////////////////////zona Desafio Abierto////////////////////////////////

void scanABIERTO(){
  while (true){
distDE=hc.dist(0);
delay(60);
distIZ=hc.dist(2);
delay(60);
if ((distDE>2)&&(distDE<90)&&(distIZ>2)&&(distIZ<90))
    {break;}
}

if (distDE > distIZ) {
   giroCCW();
   } //CCW a izquierdas

if (distDE < distIZ) {
   giroCW();
   } //CW a derechas
}

void giroCW(){

servoDireccion.write(50);
servoTraccion.write(60);
delay(1300);
servoDireccion.write(130);
servoTraccion.write(60);
delay(1200);

while(true) {
servoTraccion.write(0); 
   servoDireccion.write(dir);
distDE=hc.dist(0);
delay(30);

dir=(80-3*(-15+distDE)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección

dir = constrain(dir, 50, 130);

servoDireccion.write(dir);
    }
}

void giroCCW(){

servoDireccion.write(110);
servoTraccion.write(65);
delay(2000);
servoDireccion.write(75);
servoTraccion.write(60);
delay(1000);

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



////////////////////zona Desafio de Obstaculos////////////////////////////////


void scanOBSTACULOS(){
  while (true){
distDE=hc.dist(0);
delay(60);
distIZ=hc.dist(2);
delay(60);
if ((distDE>2)&&(distDE<90)&&(distIZ>2)&&(distIZ<90))
    {break;}
}

if (distDE > distIZ) {
   desaparcaCW();
   } //CW a izquierdas

if (distDE < distIZ) {
   desaparcaCCW();
   } //CWW a derechas
}

 
void desaparcaCW(){
  
int di = hc.dist(3);

  delay(50);
    
    if (di > 6) {
          servoTraccion.write(Retrocede);
    }
      else {

          servoTraccion.write(Para);
          delay(500);
          servoTraccion.write(100);
          servoDireccion.write(60);
          delay(3000);

          servoTraccion.write(Para);
          delay(50000);



  //giroObstCW();
      }
}






void desaparcaCCW(){

int di = hc.dist(3);

  delay(50);
    
    if (di > 6) {
          servoTraccion.write(Retrocede);
    }
      else {

          servoTraccion.write(Para);
          delay(500);
          servoTraccion.write(80);
          servoDireccion.write(120);
          delay(3000);

          servoTraccion.write(Para);
          delay(50000);

  //giroObstCCW();
      }
}





void loop() {
scan1();




}
