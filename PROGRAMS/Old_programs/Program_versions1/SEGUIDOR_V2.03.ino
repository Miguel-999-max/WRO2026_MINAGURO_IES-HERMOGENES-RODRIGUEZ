#include <HUSKYLENS.h>  //Cable verde al A4  y   cable azul al A5
#include <Wire.h>
HUSKYLENS huskylens;
const int rojo = 1;
const int verde = 2;

#include <HCSR04.h>
HCSR04 hc(2, new int[4]{3, 4, 5, 7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo servoTraccion;
Servo servoDireccion;
//Servo SERVOcam;

#define ledV 14
#define ledR 15

int i=0;
int dir=90;     
int distDE=15;  // SENSOR 0 derecho
int distFR=110; // SENSOR 1 frontal
int distIZ=15;  // SENSOR 2 izquierdo
int distTR=15;  // SENSOR 3 trasero
int ladoBusqueda = 1; 


// Variables control servos
int Izda=134;
int Dcha=54;
int Recto=94;
int Para=90;
int Avanza=0;
int Retrocede=180;
int lectura=0;
int CASO;

void setup()
{ //Serial.begin(9600);
Wire.begin(); // Iniciar el bus I2C
pinMode (12, INPUT);
pinMode (13, OUTPUT);
pinMode(ledV, OUTPUT); //led verde
pinMode(ledR, OUTPUT);  //led rojo

servoTraccion.attach(6);  // 0 AVANZA   90 STOP    180 RETROCEDE
servoDireccion.attach(9);  // 50 DCHA   90 RECTO   130 IZDA 
//SERVOcam.attach(10);      // 0 DCHA   90 RECTO   180 IZDA 
servoTraccion.write(Para);
servoDireccion.write(Recto);
//SERVOcam.write(90);

while (!huskylens.begin(Wire)) {  

    digitalWrite(13, HIGH);
    delay(1000);}
    digitalWrite(13, LOW);
delay(300);   
huskylens.writeAlgorithm(ALGORITHM_OBJECT_TRACKING);
delay(300);

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

if (distFR < 40) {
   CASO=2;   //El robot esta en el aparcamiento
   scanOBSTACULOS();
   } 
}

////////////////////zona Desafio Abierto////////////////////////////////

void scanABIERTO(){
  while (true){
servoDireccion.write(Recto);
servoTraccion.write(105); //atras despacito hasta ver el hueco con un sensor lateral
distDE=hc.dist(0);
delay(30);
distIZ=hc.dist(2);
delay(30);
if ((distDE>90)||(distIZ>90)) //detecta hueco a un lado
    { delay(30);
      servoTraccion.write(Para);
      break;}
}

if (distDE < distIZ) {
   giroCCW();
   } //CCW a izquierdas

if (distDE > distIZ) {
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

dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90

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

dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90

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
  
 distTR = hc.dist(3);

  delay(50);
    
    if (distTR > 3) {
          servoTraccion.write(100);
    }
    
    else {

          servoTraccion.write(Para);
          delay(500);
          servoDireccion.write(Dcha);
          servoTraccion.write(80);
          delay(2800);

          servoTraccion.write(Para);
          delay(50000);



giroObstCW();
      }
}

void giroObstCW(){

  if (huskylens.request() && huskylens.available()) {
    
    HUSKYLENSResult objetoCercano;
    int maxAnchoObjeto = 0;
    bool objetoEncontrado = false;

    while (huskylens.available()) {
      HUSKYLENSResult objetoActual = huskylens.read();
      
      if (objetoActual.command == COMMAND_RETURN_BLOCK) {
        if (objetoActual.width > maxAnchoObjeto) {
          maxAnchoObjeto = objetoActual.width;
          objetoCercano = objetoActual;
          objetoEncontrado = true;
        }
      }
    }
    
    if (objetoEncontrado) {
      
      if (objetoCercano.yCenter < 130) { 
        
        dir = 90 + 0.5 * (160 - objetoCercano.xCenter);
        dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90
        
        servoDireccion.write(dir); 
        servoTraccion.write(70); 
        
      } 
      else {
        servoTraccion.write(90);    
        servoDireccion.write(90);     
        
        determinarColorYSortear();
      }
      
    }
  }

  
  else if (huskylens.request() && !huskylens.available()) {
    while (true){



    }

  }



}

void determinarColorYSortear() {
  huskylens.writeAlgorithm(ALGORITHM_COLOR_RECOGNITION);
  delay(250);
  
  if (huskylens.request() && huskylens.available()) {
    
    int maxAncho = 0;
    int idColorMasCercano = 0;

    while (huskylens.available()) {
      HUSKYLENSResult bloqueActual = huskylens.read();
      
      if (bloqueActual.command == COMMAND_RETURN_BLOCK) {
        if (bloqueActual.width > maxAncho) {
          maxAncho = bloqueActual.width;
          idColorMasCercano = bloqueActual.ID;
        }
      }
    }
    
    if (idColorMasCercano == rojo) {
      
      digitalWrite(ledR, HIGH); // Enciende el led rojo como testigo de "Rojo detectado"
      delay(2000);
      digitalWrite(ledR, LOW);
      servoDireccion.write(Dcha); // Dcha 50
      servoTraccion.write(80); 
      delay(1000);
      servoDireccion.write(90);
      delay(2500);
      servoTraccion.write(90);   
      servoDireccion.write(90);    
      delay(5000);

    } 
    else if (idColorMasCercano == verde) {

      digitalWrite(ledV, HIGH); // Enciende el led verde como testigo de "Verde detectado"
      delay(2000);
      digitalWrite(ledV, LOW);
      servoDireccion.write(Izda); // Izda 130
      servoTraccion.write(80); 
      delay(1000);
      servoDireccion.write(90);
      delay(2500);
      servoTraccion.write(90);  
      servoDireccion.write(90);    
      delay(5000);

    }
}
huskylens.writeAlgorithm(ALGORITHM_OBJECT_TRACKING);
delay(300);

giroObstCW();
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




